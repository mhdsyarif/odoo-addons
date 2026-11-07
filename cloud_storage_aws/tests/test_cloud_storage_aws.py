from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

from odoo.tests.common import tagged, TransactionCase
from odoo.exceptions import UserError
from odoo.http.stream import content_disposition

from .. import uninstall_hook

CLIENT_PATH = 'odoo.addons.cloud_storage_aws.models.ir_attachment'


class TestCloudStorageAWSCommon(TransactionCase):
    def setUp(self):
        super().setUp()
        self.bucket_name = 'bucket-name'
        self.region = 'ap-southeast-3'
        ICP = self.env['ir.config_parameter']
        ICP.set_str('cloud_storage_provider', 'aws')
        ICP.set_str('cloud_storage_aws_bucket_name', self.bucket_name)
        ICP.set_str('cloud_storage_aws_region', self.region)
        ICP.set_str('cloud_storage_aws_access_key_id', 'AKIAIOSFODNN7EXAMPLE')
        ICP.set_str('cloud_storage_aws_secret_access_key', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY')


@tagged('post_install', '-at_install')
class TestCloudStorageAWS(TestCloudStorageAWSCommon):
    def test_generate_signed_url(self):
        file_name = ' ¥®°²Æçéðπ⁉€∇⓵▲☑♂♥✓➔『にㄅ㊀中한︸🌈🌍👌😀.txt'
        attachment = self.env['ir.attachment'].create([{
            'name': file_name,
            'mimetype': 'text/plain',
            'raw': b'',
        }])
        attachment._post_add_create(cloud_storage=True)
        base_url = f'https://{self.bucket_name}.s3.{self.region}.amazonaws.com/'
        self.assertTrue(attachment.url.startswith(base_url))
        self.assertRegex(
            attachment._get_cloud_storage_aws_info()['blob_name'],
            rf'^{self.env.cr.dbname}/{attachment.id}/[0-9a-f]{{64}}\.txt$',
        )
        self.assertNotIn(quote(file_name), attachment.url)

        upload_info = attachment._generate_cloud_storage_upload_info()
        self.assertTrue(upload_info['url'].startswith(base_url))
        self.assertIn('X-Amz-Signature=', upload_info['url'])
        self.assertEqual(upload_info['headers'], {'Content-Type': 'text/plain'})

        download_info = attachment._generate_cloud_storage_download_info()
        self.assertTrue(download_info['url'].startswith(base_url))
        self.assertIn('X-Amz-Signature=', download_info['url'])
        # the original file name is given back by S3
        query = parse_qs(urlsplit(download_info['url']).query)
        self.assertEqual(query['response-content-disposition'], [content_disposition(file_name, 'inline')])

    def _create_aws_attachment(self, name='test.txt'):
        attachment = self.env['ir.attachment'].create([{
            'name': name,
            'mimetype': 'text/plain',
            'raw': b'',
        }])
        attachment._post_add_create(cloud_storage=True)
        return attachment

    def _run_delete_blobs_postcommit(self):
        """Run only the S3 deletion callbacks, the other postcommit callbacks must not run in tests."""
        funcs = self.env.cr.postcommit._funcs
        for func in [func for func in funcs if func.__name__ == 'delete_blobs']:
            funcs.remove(func)
            func()

    def test_server_side_upload(self):
        """Attachments uploaded without the cloud_storage flag (e.g. many2many_binary) are pushed to S3 by the server."""
        ICP = self.env['ir.config_parameter']
        ICP.set_bool('cloud_storage_upload_record_attachments', True)
        ICP.set_int('cloud_storage_min_file_size', 0)
        partner = self.env['res.partner'].create({'name': 'Test'})
        attachment = self.env['ir.attachment'].create([{
            'name': 'photo.txt',
            'mimetype': 'text/plain',
            'raw': b'hello',
            'res_model': partner._name,
            'res_id': partner.id,
        }])
        with patch(f'{CLIENT_PATH}.get_cloud_storage_aws_client') as get_client:
            attachment._post_add_create()
        get_client.return_value.put_object.assert_called_once()
        kwargs = get_client.return_value.put_object.call_args.kwargs
        self.assertEqual(kwargs['Bucket'], self.bucket_name)
        self.assertEqual(kwargs['Body'], b'hello')
        self.assertEqual(attachment.type, 'cloud_storage')
        self.assertEqual(attachment._get_cloud_storage_aws_info()['blob_name'], kwargs['Key'])
        self.assertFalse(attachment.store_fname)

    def test_server_side_upload_below_min_size(self):
        ICP = self.env['ir.config_parameter']
        ICP.set_bool('cloud_storage_upload_record_attachments', True)
        ICP.set_int('cloud_storage_min_file_size', 100)
        attachment = self.env['ir.attachment'].create([{'name': 'small.txt', 'raw': b'hello'}])
        with patch(f'{CLIENT_PATH}.get_cloud_storage_aws_client') as get_client:
            attachment._post_add_create()
        get_client.return_value.put_object.assert_not_called()
        self.assertEqual(attachment.type, 'binary')

    def test_unlink_deletes_blob(self):
        attachment = self._create_aws_attachment()
        blob_name = attachment._get_cloud_storage_aws_info()['blob_name']
        with patch(f'{CLIENT_PATH}.get_cloud_storage_aws_client') as get_client:
            attachment.unlink()
            get_client.return_value.delete_objects.assert_not_called()  # only after commit
            self._run_delete_blobs_postcommit()
        get_client.return_value.delete_objects.assert_called_once_with(
            Bucket=self.bucket_name,
            Delete={'Objects': [{'Key': blob_name}], 'Quiet': True},
        )

    def test_unlink_keeps_shared_blob(self):
        attachment = self._create_aws_attachment()
        attachment_copy = attachment.copy()
        self.assertEqual(attachment_copy.url, attachment.url)
        with patch(f'{CLIENT_PATH}.get_cloud_storage_aws_client') as get_client:
            attachment.unlink()
            self._run_delete_blobs_postcommit()
        get_client.return_value.delete_objects.assert_not_called()

    def test_uninstall_fail(self):
        with self.assertRaises(UserError, msg="Don't uninstall the module if there are AWS attachments in use"):
            attachment = self.env['ir.attachment'].create([{
                'name': 'test.txt',
                'mimetype': 'text/plain',
                'raw': b'',
            }])
            attachment._post_add_create(cloud_storage=True)
            attachment.flush_recordset()
            uninstall_hook(self.env)

    def test_uninstall_success(self):
        # ignore the real AWS attachments of the database (rolled back after the test)
        self.env.cr.execute("UPDATE ir_attachment SET type = 'url' WHERE type = 'cloud_storage'")
        uninstall_hook(self.env)
        # make sure all sensitive data are removed
        ICP = self.env['ir.config_parameter']
        self.assertFalse(ICP.get_str('cloud_storage_provider'))
        self.assertFalse(ICP.get_str('cloud_storage_aws_bucket_name'))
        self.assertFalse(ICP.get_str('cloud_storage_aws_region'))
        self.assertFalse(ICP.get_str('cloud_storage_aws_access_key_id'))
        self.assertFalse(ICP.get_str('cloud_storage_aws_secret_access_key'))
