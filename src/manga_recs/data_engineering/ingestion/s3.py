import boto3
import os
from dotenv import load_dotenv
from datetime import datetime

# Load env vars
load_dotenv()

def s3_dump(filepath: str, filename: str, bucket: str = 'manga-recs'):
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
    S3_PREFIX = f"raw/{today_str}/"

    try:
        s3.upload_file(filepath, bucket, f'{S3_PREFIX}{filename}')
        print(f"Uploaded {filename} to s3://{bucket}/{S3_PREFIX}{filename}")
    except Exception as e:
        print(f"Error uploading {filename}: {e}")