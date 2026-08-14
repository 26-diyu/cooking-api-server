The command to run

uvicorn main:app --host 0.0.0.0 --port 8027 --ssl-certfile ./localhost+1.pem --ssl-keyfile ./localhost+1-key.pem

For Ollama response time improvement, on Windows PowerShell

[System.Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')
[System.Environment]::SetEnvironmentVariable('NUM_BATCH', '2048', 'User')
[System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '0', 'User')