#!/bin/bash

exec uvicorn --port $PORT main:app
