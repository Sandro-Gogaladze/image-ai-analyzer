import io
import json
import base64
import uuid
import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from datetime import datetime
from decimal import Decimal
from urllib.request import urlopen, Request
import os

s3_client = boto3.client("s3")
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
S3_BUCKET = os.environ["S3_BUCKET"]
HF_API_TOKEN = os.environ["HF_API_TOKEN"]

MODELS = {
    "detr-resnet-50":            "https://router.huggingface.co/hf-inference/models/facebook/detr-resnet-50",
    "vit-base-patch16-224":      "https://router.huggingface.co/hf-inference/models/google/vit-base-patch16-224",
    "resnet-50":                 "https://router.huggingface.co/hf-inference/models/microsoft/resnet-50",
}


def query_huggingface(image_bytes, model_key):
    api_url = MODELS.get(model_key, MODELS["detr-resnet-50"])
    req = Request(
        api_url,
        data=image_bytes,
        headers={
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "image/jpeg",
        },
        method="POST",
    )
    with urlopen(req, timeout=60) as response:
        return response.read().decode()


def save_to_s3(image_bytes, filename):
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=filename,
        Body=image_bytes,
        ContentType="image/jpeg",
    )
    return f"s3://{S3_BUCKET}/{filename}"


def save_to_dynamodb(hf_result, s3_url, model_key, filename):
    dynamodb = boto3.client("dynamodb")
    serializer = TypeSerializer()
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat()

    parsed = json.loads(hf_result, parse_float=Decimal)

    # Serialize HuggingFace JSON list
    if isinstance(parsed, list):
        hf_serialized = []
        for item in parsed:
            dynamo_item = {"M": {}}
            for k, v in item.items():
                if isinstance(v, (float, Decimal)):
                    dynamo_item["M"][k] = {"N": str(v)}
                elif isinstance(v, dict):
                    dynamo_item["M"][k] = {"M": {ik: serializer.serialize(iv) for ik, iv in v.items()}}
                else:
                    dynamo_item["M"][k] = {"S": str(v)}
            hf_serialized.append(dynamo_item)
        hf_dynamo = {"L": hf_serialized}
    else:
        hf_dynamo = {"S": str(parsed)}

    item = {
        "id":                   {"S": str(uuid.uuid1())},
        "createdAt":            {"S": timestamp},
        "updatedAt":            {"S": timestamp},
        "model":                {"S": model_key},
        "filename":             {"S": filename},
        "s3Url":                {"S": s3_url},
        "huggingFaceStringData":{"S": hf_result},
        "huggingJson":          hf_dynamo,
    }

    try:
        dynamodb.put_item(TableName=DYNAMODB_TABLE, Item=item)
    except ClientError as e:
        print(e.response["Error"]["Message"])
        raise e


def lambda_handler(event, _):
    try:
        body = event.get("body", "")
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body)
            parsed = json.loads(body)
        else:
            parsed = json.loads(body)

        image_b64 = parsed["image"]        # base64 string
        model_key = parsed.get("model", "detr-resnet-50")
        filename  = parsed.get("filename", f"{uuid.uuid4()}.jpg")

        image_bytes = base64.b64decode(image_b64)

        # 1. Save to S3
        s3_url = save_to_s3(image_bytes, filename)
        print(f"Saved to S3: {s3_url}")

        # 2. Send to HuggingFace
        hf_result = query_huggingface(image_bytes, model_key)
        print(f"HuggingFace result: {hf_result}")

        # 3. Save to DynamoDB
        save_to_dynamodb(hf_result, s3_url, model_key, filename)
        print("Saved to DynamoDB")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "message": "Success!",
                "model": model_key,
                "filename": filename,
                "s3_url": s3_url,
                "result": json.loads(hf_result),
            }),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
