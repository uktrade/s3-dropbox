#!/bin/bash

exec uvicorn --port $PORT main:app --host 0.0.0.0
