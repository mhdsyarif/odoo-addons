import hashlib
import logging
import os
import re
import uuid
from collections import defaultdict
from urllib.parse import quote, unquote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from odoo import models
from odoo.exceptions import ValidationError
from odoo.http.stream import content_disposition
from odoo.tools import split_every

from odoo.addons.cloud_storage.models.res_config_settings import DEFAULT_CLOUD_STORAGE_MIN_FILE_SIZE

_logger = logging.getLogger(__name__)

CloudStorageAWSClients = {}  # {db_name: (credentials, client)}
S3_DELETE_OBJECTS_BATCH_SIZE = 1000  # max keys accepted by DeleteObjects


def get_cloud_storage_aws_client(env):
    """ Get the S3 client of currently used credentials.
    This method is cached because creating a boto3 client is slow.
    """
    ICP = env['ir.config_parameter'].sudo()
    region = (ICP.get_str('cloud_storage_aws_region') or '').strip()
    access_key_id = (ICP.get_str('cloud_storage_aws_access_key_id') or '').strip()
    secret_access_key = (ICP.get_str('cloud_storage_aws_secret_access_key') or '').strip()
    credentials = (region, access_key_id, secret_access_key)
    cached_credentials, cached_client = CloudStorageAWSClients.get(env.registry.db_name, (None, None))
    if cached_credentials == credentials:
        return cached_client
    client = boto3.client(
        's3',
        region_name=region or None,
        # force the regional endpoint so that signed urls match the blob urls
        endpoint_url=f'https://s3.{region}.amazonaws.com' if region else None,
        aws_access_key_id=access_key_id or None,
        aws_secret_access_key=secret_access_key or None,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
    )
    CloudStorageAWSClients[env.registry.db_name] = (credentials, client)
    return client


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'
    _cloud_storage_aws_url_pattern = re.compile(r'^https://(?P<bucket_name>[\w\-.]+)\.s3\.(?P<region>[\w\-]+)\.amazonaws\.com/(?P<blob_name>[^?]+)$')

    def _get_cloud_storage_aws_info(self):
        match = self._cloud_storage_aws_url_pattern.fullmatch(self.url or '')
        if not match:
            raise ValidationError(self.env._('%s is not a valid AWS S3 URL.', self.url))
        return {
            'bucket_name': match['bucket_name'],
            'region': match['region'],
            'blob_name': unquote(match['blob_name']),
        }

    def _generate_cloud_storage_aws_url(self, blob_name):
        ICP = self.env['ir.config_parameter'].sudo()
        bucket_name = (ICP.get_str('cloud_storage_aws_bucket_name') or '').strip()
        region = (ICP.get_str('cloud_storage_aws_region') or '').strip()
        return f"https://{bucket_name}.s3.{region}.amazonaws.com/{quote(blob_name)}"

    def _generate_cloud_storage_aws_signed_url(self, bucket_name, blob_name, method='GET', expiration=300, **params):
        client_method = {'GET': 'get_object', 'PUT': 'put_object'}[method]
        return get_cloud_storage_aws_client(self.env).generate_presigned_url(
            ClientMethod=client_method,
            Params={'Bucket': bucket_name, 'Key': blob_name, **{k: v for k, v in params.items() if v}},
            ExpiresIn=expiration,
            HttpMethod=method,
        )

    def _generate_cloud_storage_aws_blob_name(self):
        """ <database>/<attachment id>/<hashed file name>.<extension>
        The file name is hashed with a random salt so that blob names are
        unguessable and do not leak the file name, the original name is given
        back when downloading (see Content-Disposition).
        """
        _, extension = os.path.splitext(self.name or '')
        if not re.fullmatch(r'\.\w{1,10}', extension):
            extension = ''
        hashed_name = hashlib.sha256(f'{uuid.uuid4()}{self.name}'.encode()).hexdigest()
        return f'{self.env.cr.dbname}/{self.id}/{hashed_name}{extension.lower()}'

    # OVERRIDES
    def _generate_cloud_storage_blob_name(self):
        if self.env['ir.config_parameter'].sudo().get_str('cloud_storage_provider') != 'aws':
            return super()._generate_cloud_storage_blob_name()
        return self._generate_cloud_storage_aws_blob_name()

    def _generate_cloud_storage_url(self):
        if self.env['ir.config_parameter'].sudo().get_str('cloud_storage_provider') != 'aws':
            return super()._generate_cloud_storage_url()
        blob_name = self._generate_cloud_storage_blob_name()
        return self._generate_cloud_storage_aws_url(blob_name)

    def _generate_cloud_storage_download_info(self):
        if self.env['ir.config_parameter'].sudo().get_str('cloud_storage_provider') != 'aws':
            return super()._generate_cloud_storage_download_info()
        info = self._get_cloud_storage_aws_info()
        time_to_expiry = self._get_cloud_storage_download_url_time_to_expiry()
        return {
            'url': self._generate_cloud_storage_aws_signed_url(
                info['bucket_name'], info['blob_name'],
                method='GET',
                expiration=time_to_expiry,
                ResponseContentType=self.mimetype or None,
                # the blob name is hashed, always give back the original file name
                ResponseContentDisposition=content_disposition(
                    self.name, 'attachment' if self.env.context.get('download_attachments') else 'inline',
                ) if self.name else None,
            ),
            'time_to_expiry': time_to_expiry,
        }

    def _generate_cloud_storage_upload_info(self):
        if self.env['ir.config_parameter'].sudo().get_str('cloud_storage_provider') != 'aws':
            return super()._generate_cloud_storage_upload_info()
        info = self._get_cloud_storage_aws_info()
        return {
            'url': self._generate_cloud_storage_aws_signed_url(
                info['bucket_name'], info['blob_name'],
                method='PUT',
                expiration=self._cloud_storage_upload_url_time_to_expiry,
                # the signature includes the content type, the client must send the same header
                ContentType=self.mimetype or None,
            ),
            'method': 'PUT',
            'response_status': 200,
            'headers': {'Content-Type': self.mimetype} if self.mimetype else {},
        }

    def _post_add_create(self, **kwargs):
        super()._post_add_create(**kwargs)
        if not kwargs.get('cloud_storage'):
            # the web client only uploads directly to the cloud from the
            # chatter, upload the other ones (e.g. many2many_binary) from here
            self._cloud_storage_aws_upload_from_server()

    def _cloud_storage_aws_upload_from_server(self):
        ICP = self.env['ir.config_parameter'].sudo()
        if (
            ICP.get_str('cloud_storage_provider') != 'aws'
            or not self.env['res.config.settings']._get_cloud_storage_configuration()
        ):
            return
        min_file_size = ICP.get_int('cloud_storage_min_file_size', DEFAULT_CLOUD_STORAGE_MIN_FILE_SIZE)
        unsupported_models = self._get_cloud_storage_unsupported_models()
        attachments = self.filtered(lambda a: (
            a.type == 'binary'
            and a.raw
            and a.file_size > min_file_size
            and a.res_model not in unsupported_models
        ))
        client = get_cloud_storage_aws_client(self.env)
        for attachment in attachments:
            url = attachment._generate_cloud_storage_url()
            info = attachment._get_cloud_storage_aws_info_from_url(url)
            client.put_object(
                Bucket=info['bucket_name'],
                Key=info['blob_name'],
                Body=bytes(attachment.raw or b''),
                ContentType=attachment.mimetype or 'application/octet-stream',
            )
            attachment.write({
                # Preserve the existing mimetype to avoid it being guessed
                'mimetype': attachment.mimetype,
                'raw': False,
                'type': 'cloud_storage',
                'url': url,
            })

    def _get_cloud_storage_aws_info_from_url(self, url):
        return self.new({'url': url})._get_cloud_storage_aws_info()

    def unlink(self):
        urls = {
            attachment.url for attachment in self
            if attachment.type == 'cloud_storage'
            and self._cloud_storage_aws_url_pattern.fullmatch(attachment.url or '')
        }
        res = super().unlink()
        if urls:
            self._cloud_storage_aws_delete_blobs(urls)
        return res

    def _cloud_storage_aws_delete_blobs(self, urls):
        """ Delete the blobs of the given urls from S3 once the transaction is
        committed, unless another attachment (e.g. a copy) still uses them.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if not (ICP.get_str('cloud_storage_aws_access_key_id') and ICP.get_str('cloud_storage_aws_secret_access_key')):
            _logger.warning('AWS credentials are missing, %d S3 blobs are not deleted', len(urls))
            return
        self.env.cr.execute(
            "SELECT url FROM ir_attachment WHERE type = 'cloud_storage' AND url = ANY(%s)",
            [list(urls)],
        )
        urls -= {url for (url,) in self.env.cr.fetchall()}
        keys_by_bucket = defaultdict(list)
        for url in urls:
            info = self._get_cloud_storage_aws_info_from_url(url)
            keys_by_bucket[info['bucket_name']].append(info['blob_name'])
        if not keys_by_bucket:
            return
        client = get_cloud_storage_aws_client(self.env)

        def delete_blobs():
            for bucket_name, keys in keys_by_bucket.items():
                for batch in split_every(S3_DELETE_OBJECTS_BATCH_SIZE, keys, list):
                    try:
                        response = client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': [{'Key': key} for key in batch], 'Quiet': True},
                        )
                    except (BotoCoreError, ClientError):
                        _logger.exception('Failed to delete %d blobs from S3 bucket %s', len(batch), bucket_name)
                        continue
                    for error in response.get('Errors', []):
                        _logger.warning('Failed to delete S3 blob %s: %s', error.get('Key'), error.get('Message'))
        self.env.cr.postcommit.add(delete_blobs)
