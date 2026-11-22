import json
import os
import httpx
import asyncio


async def _call_endpoint(client, method, path, json_body=None):
    base_url = os.environ.get("XNCH_BASE_URL")
    if not base_url:
        return {"error": "XNCH_BASE_URL not set"}
    url = f"{base_url}{path}"
    try:
        if method == "GET":
            resp = await client.get(url)
        elif method == "POST":
            resp = await client.post(url, json=json_body)
        else:
            return {"error": f"Unsupported method: {method}"}
        return {
            "status": resp.status_code,
            "body": resp.text[:500],
        }
    except Exception as exc:
        return {"error": str(exc)}


async def run():
    async with httpx.AsyncClient(timeout=30.0) as client:
        result = await _call_endpoint(
            client, "POST", "/api/pipeline/run",
            json_body={"job": "policy_evolver"}
        )
    return result


def lambda_handler(event, context):
    result = asyncio.run(run())
    return {
        "statusCode": 200,
        "body": json.dumps(result),
    }