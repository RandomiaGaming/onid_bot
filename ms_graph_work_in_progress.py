import msal
import os
import json
import requests

from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
import asyncio

# Sending emails.
def SendEmail(to: str, subject: str, body: str) -> None:
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }

    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token_info = response.json()
    token = token_info["access_token"]

    headers = { "Authorization": f"Bearer {token}", "Accept": "application/json", "Content-type": "application/json" }
    request = {
        "message": {
            "subject": "Meet for lunch?",
            "body": {
                "contentType": "Text",
                "content": "The new cafeteria is open."
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "christj@oregonstate.edu"
                    }
                }
            ]
        }
    }
    response = requests.post(f"https://graph.microsoft.com/v1.0/users/{ENV.graph_email}/sendMail", json=request, headers=headers)
    response.raise_for_status()
    response_object = response.json()
SendEmail("christj@oregonstate.edu", "Ligma", "Balls")

# App registration details

# You can try either of these:
scopes = ["https://graph.microsoft.com/Mail.Send"]
# scopes = ["Mail.Send"]

def get_token():
    app = msal.PublicClientApplication(
        client_id=client_id
    )

    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise Exception("Failed to create device flow")
    print(flow["message"])  # "To sign in, use a web browser to open ..."

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        print("✅ Got token")
        return result["access_token"]
    else:
        raise Exception(f"Failed to acquire token: {result}")

# Example usage
token = get_token()
print("Access token:", token[:40], "...")  # Print prefix only for sanity check

email_address = "Indoor.RockClimbing@oregonstate.edu"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

message = {
    "message": {
        "subject": "Climb night reminder",
        "body": {
            "contentType": "Text",
            "content": "Bring your shoes and chalk!"
        },
        "toRecipients": [
            {"emailAddress": {"address": "christj@oregonstate.edu"}}
        ]
    },
    "saveToSentItems": True
}

resp = requests.post(f"https://graph.microsoft.com/v1.0/users/{email_address}/sendMail", headers=headers, json=message)
print(resp.status_code, resp.text)