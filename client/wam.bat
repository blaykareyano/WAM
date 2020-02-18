@echo off
SET currpath=%~dp0
SET script=wam.py
SET scriptpath=%currpath%%script%
python %scriptpath% %*