import uuid

import requests
from botocore.exceptions import BotoCoreError, ClientError

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from .ir_attachment import get_cloud_storage_aws_client


class ResConfigSettings(models.TransientModel):
    """
    Instructions:
    cloud_storage_aws_bucket_name: if changed and the old bucket name
        are still in use, you should promise the current access key
        has the permission to access the old bucket.
    The IAM user needs s3:PutObject, s3:GetObject, s3:DeleteObject and
    s3:PutBucketCORS permissions on the bucket.
    """
    _inherit = 'res.config.settings'

    cloud_storage_provider = fields.Selection(selection_add=[('aws', 'Amazon S3')])

    cloud_storage_aws_bucket_name = fields.Char(
        string='S3 Bucket Name',
        help='Avoid dots (.) in the bucket name to prevent SSL certificate verification issues with virtual-hosted style URLs.',
        config_parameter='cloud_storage_aws_bucket_name')
    cloud_storage_aws_region = fields.Char(
        string='S3 Region',
        help='e.g. ap-southeast-3',
        config_parameter='cloud_storage_aws_region')
    cloud_storage_aws_access_key_id = fields.Char(
        string='AWS Access Key ID',
        config_parameter='cloud_storage_aws_access_key_id')
    cloud_storage_aws_secret_access_key = fields.Char(
        string='AWS Secret Access Key',
        config_parameter='cloud_storage_aws_secret_access_key')

    def _setup_cloud_storage_provider(self):
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_str('cloud_storage_provider') != 'aws':
            return super()._setup_cloud_storage_provider()
        # check bucket access
        bucket_name = (ICP.get_str('cloud_storage_aws_bucket_name') or '').strip()
        # use random hex blob names to avoid special characters (: and spaces)
        # in S3 SigV4 signature calculations and prevent collisions
        blob_name = f'{self.env.cr.dbname}/0/{uuid.uuid4().hex}.txt'

        IrAttachment = self.env['ir.attachment']
        time_to_expiry = IrAttachment._get_cloud_storage_download_url_time_to_expiry()

        # check blob create permission
        upload_url = IrAttachment._generate_cloud_storage_aws_signed_url(
            bucket_name, blob_name, method='PUT', expiration=IrAttachment._cloud_storage_upload_url_time_to_expiry
        )
        try:
            upload_response = requests.put(upload_url, data=b'', timeout=5)
            if upload_response.status_code != 200:
                raise ValidationError(_('The access key is not allowed to upload blobs to the bucket.\n%s', str(upload_response.text)))
        except requests.exceptions.RequestException as e:
            raise ValidationError(_('Failed to connect to AWS S3 for upload test:\n%s', str(e)))

        # check blob read permission
        download_url = IrAttachment._generate_cloud_storage_aws_signed_url(
            bucket_name, blob_name, method='GET', expiration=time_to_expiry
        )
        try:
            download_response = requests.get(download_url, timeout=5)
            if download_response.status_code != 200:
                raise ValidationError(_('The access key is not allowed to download blobs from the bucket.\n%s', str(download_response.text)))
        except requests.exceptions.RequestException as e:
            raise ValidationError(_('Failed to connect to AWS S3 for download test:\n%s', str(e)))

        client = get_cloud_storage_aws_client(self.env)
        # check blob delete permission, it also cleans up the test blob
        try:
            client.delete_object(Bucket=bucket_name, Key=blob_name)
        except (BotoCoreError, ClientError) as e:
            raise ValidationError(_('The access key is not allowed to delete blobs from the bucket.\n%s', str(e)))

        # configure CORS on bucket to allow .pdf preview and direct upload
        cors = {'CORSRules': [{
            'AllowedOrigins': ['*'],
            'AllowedMethods': ['GET', 'PUT'],
            'AllowedHeaders': ['*'],
            'ExposeHeaders': ['Content-Type', 'Content-Disposition', 'ETag'],
            'MaxAgeSeconds': time_to_expiry,
        }]}
        try:
            client.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors)
        except (BotoCoreError, ClientError) as e:
            raise ValidationError(_("The access key is not allowed to set the bucket's CORS.\n%s", str(e)))

    def _get_cloud_storage_configuration(self):
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_str('cloud_storage_provider') != 'aws':
            return super()._get_cloud_storage_configuration()
        bucket = ICP.get_str('cloud_storage_aws_bucket_name')
        region = ICP.get_str('cloud_storage_aws_region')
        key_id = ICP.get_str('cloud_storage_aws_access_key_id')
        secret = ICP.get_str('cloud_storage_aws_secret_access_key')
        configuration = {
            'bucket_name': bucket.strip() if bucket else None,
            'region': region.strip() if region else None,
            'access_key_id': key_id.strip() if key_id else None,
            'secret_access_key': secret.strip() if secret else None,
        }
        return configuration if all(configuration.values()) else {}

    def _check_cloud_storage_uninstallable(self):
        if self.env['ir.config_parameter'].sudo().get_str('cloud_storage_provider') != 'aws':
            return super()._check_cloud_storage_uninstallable()
        cr = self.env.cr
        cr.execute(
            """
                SELECT type
                FROM ir_attachment
                WHERE type = 'cloud_storage'
                AND url LIKE 'https://%.amazonaws.com/%'
                LIMIT 1
            """,
        )
        if cr.fetchone():
            raise UserError(_('Some AWS attachments are in use, please migrate cloud storages before disabling the provider'))
