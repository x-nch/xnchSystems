#!/bin/bash
# Run once on i7 after cluster is up.
set -e

NS=xnch-system

kubectl create secret generic postgres-secret -n $NS --dry-run=client -o yaml   --from-literal=password=e369ee6226bca8f4d9db2bea70687d85ec6f318643a1dff0813c79bb11bfabbf | kubectl apply -f -

kubectl create secret generic xnch-secret -n $NS --dry-run=client -o yaml   --from-literal=postgres_password=e369ee6226bca8f4d9db2bea70687d85ec6f318643a1dff0813c79bb11bfabbf   --from-literal=auth_secret=52b31c9d99970d9294f10103a493c7567a2150303b95336ca18b42280364373f | kubectl apply -f -

kubectl create secret generic langfuse-secret -n $NS --dry-run=client -o yaml   --from-literal=nextauth_secret=6edd023434ebea3c7cba050f74a2eaaaccc71cc3700c1b840d3a06f9a73d1d81   --from-literal=salt=5c7c79772cea2a120f50f38c82d12245f13d8ea914aba41f54c4eb142fcb6c6e | kubectl apply -f -

kubectl create secret generic litellm-secret -n $NS --dry-run=client -o yaml   --from-literal=master_key=df4d178833bb37cac13628dcf2ce970e5d98e298f1c53eed8baadfe8e505b91d | kubectl apply -f -

kubectl create secret generic huggingface-secret -n $NS --dry-run=client -o yaml   --from-literal=token=YOUR_HF_TOKEN_HERE | kubectl apply -f -

kubectl create secret generic zep-secret -n $NS --dry-run=client -o yaml   --from-literal=openai_api_key=YOUR_OPENAI_API_KEY_HERE | kubectl apply -f -

echo "All secrets created"
