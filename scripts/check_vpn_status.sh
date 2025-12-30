#!/bin/bash
VPS_HOST="74.208.167.166"
echo "Checking WireGuard Status on VPS..."
echo "Enter password: DCaoY6yl"

ssh root@$VPS_HOST "docker exec netguard-wireguard wg show"
