DELETE FROM ir_config_parameter
WHERE key IN (
    'cloud_storage_aws_bucket_name',
    'cloud_storage_aws_region',
    'cloud_storage_aws_access_key_id',
    'cloud_storage_aws_secret_access_key'
);
