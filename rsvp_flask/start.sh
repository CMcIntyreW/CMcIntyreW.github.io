#!/bin/sh
# Wrapper so PORT is expanded at runtime (Railway injects it)
exec gunicorn -w 1 -b "0.0.0.0:${PORT:-5000}" app:app
