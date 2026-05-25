import json
import os


def _is_configured():
    return bool(os.environ.get('R2_ACCOUNT_ID'))


def _client():
    import boto3
    return boto3.client(
        's3',
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
    )


def get_json(key, local_fallback=None, default=None):
    if not _is_configured():
        if local_fallback and os.path.exists(local_fallback):
            with open(local_fallback, 'r') as f:
                return json.load(f)
        return default
    try:
        obj = _client().get_object(Bucket=os.environ['R2_BUCKET_NAME'], Key=key)
        return json.loads(obj['Body'].read())
    except Exception:
        return default


def put_json(key, data, local_fallback=None):
    if not _is_configured():
        if local_fallback:
            os.makedirs(os.path.dirname(local_fallback) or '.', exist_ok=True)
            with open(local_fallback, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return
    _client().put_object(
        Bucket=os.environ['R2_BUCKET_NAME'],
        Key=key,
        Body=json.dumps(data, indent=2, ensure_ascii=False).encode(),
        ContentType='application/json',
    )
