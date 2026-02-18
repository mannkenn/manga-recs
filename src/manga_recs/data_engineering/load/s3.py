import boto3
import os
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Load env vars
load_dotenv()

def s3_dump(filepath: str, filename: str, bucket: str = 'manga-recs', status: str = 'raw'):
    '''
    Dumps json to s3 bucket
    '''

    # Connet to s3 
    s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION")
    )

    # Versioning
    today_str = datetime.today().strftime("%Y-%m-%d")
    S3_PREFIX = f"{status}/{today_str}/"

    try:
        s3.upload_file(filepath, bucket, f'{S3_PREFIX}{filename}')
        print(f"Uploaded {filename} to s3://{bucket}/{S3_PREFIX}{filename}")
    except Exception as e:
        print(f"Error uploading {filename}: {e}")


def get_latest_s3_file(bucket: str = 'manga-recs', status: str = 'raw'):
    '''
    Gets latest file from s3 bucket
    '''
    # Connet to s3 
    s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION")
    )

    # Get latest version of file
    response = s3.list_objects_v2(Bucket=bucket, Prefix=f'{status}/')

    if "Contents" not in response:
        raise FileNotFoundError(f"No objects found under {status}")
    
    folders = set()

    for obj in response["Contents"]:
        key = obj["Key"]
        parts = key.split('/')
        if len(parts) > 1:
            folders.add(parts[1])

    latest = max(folders, key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
    
    return latest

def s3_load(filename: str, bucket: str = 'manga-recs', status: str = 'raw', use_cache: bool = True):
    """
    Download file from S3 if not already cached locally.
    Returns local path to file.
    """

    # Local folder
    download_dir = Path("data") / status
    download_dir.mkdir(parents=True, exist_ok=True)
    local_path = download_dir / filename

    # Check if file exists and use_cache is True
    if use_cache and local_path.exists():
        print(f"Using cached file at {local_path}")
        return str(local_path)

    # Connect to S3
    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION")
    )

    latest_version = get_latest_s3_file(bucket, status)

    try:
        s3.download_file(bucket, f'{status}/{latest_version}/{filename}', str(local_path))
        print(f"Downloaded {filename} from s3://{bucket}/{status}/{latest_version}/{filename}")
    except Exception as e:
        print(f"Error downloading {filename}: {e}")

    return str(local_path)
