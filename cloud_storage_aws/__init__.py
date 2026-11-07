from . import models


def uninstall_hook(env):
    ICP = env['ir.config_parameter'].sudo()
    if ICP.get_str('cloud_storage_provider') == 'aws':
        env['res.config.settings']._check_cloud_storage_uninstallable()
        ICP.set_str('cloud_storage_provider', None)
    ICP.search([('key', 'in', [
        'cloud_storage_aws_bucket_name',
        'cloud_storage_aws_region',
        'cloud_storage_aws_access_key_id',
        'cloud_storage_aws_secret_access_key',
    ])]).unlink()
