@echo off
setlocal

set "HR_URL=http://192.168.128.70:5000/login"

echo Opening HKR HR web app:
echo %HR_URL%
start "" "%HR_URL%"
