# Helper script to launch local Ollama with custom models directory
$env:OLLAMA_MODELS = "D:\AI_Models\Ollama"
$env:OLLAMA_HOST = "127.0.0.1:11434"
Write-Host "Starting Ollama server on 127.0.0.1:11434 with models at $env:OLLAMA_MODELS..."
ollama serve

