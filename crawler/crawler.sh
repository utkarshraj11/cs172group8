#! /bin/bash

YELLOW='\033[0;33m' 
RED='\033[0;31m'
NC='\033[0m' # No Color reset

if [ "$#" -ne 5 ]; then
    echo -e "${YELLOW}Usage: $0 <seed-file> <max-depth> <time-limit_secs> <max-size-MB> <output.json>${NC}"
    exit 1
fi

SEED_FILE=$1
MAX_DEPTH=$2
TIME_LIMIT=$3
MAX_SIZE=$4
OUTPUT_FILE=$5

if [ ! -f "$SEED_FILE" ]; then
    echo -e "${RED}Err: Specified Seed file not found!${NC}"
    exit 1
fi

# Separate URLs by space
SEED_URLS=$(tr '\n' ' ' < "$SEED_FILE")

python3 crawler.py "$SEED_URLS" "$MAX_DEPTH" "$TIME_LIMIT" "$MAX_SIZE" "$OUTPUT_FILE"
