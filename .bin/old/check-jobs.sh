#!/bin/bash

for user in {jjensen,sbutler,cmayberry,jemerson,rmartinez} ; do
	echo ""
	echo "===== $user ====="
	kubectl get jobs -l validation.groq.io/created-by="$user"
done
