# Noveris AI - 环境初始化脚本 (PowerShell)
# 支持: Windows PowerShell

param(
    [switch]$SkipChecks,
    [switch]$Force
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )

    $ColorMap = @{
        "Red" = [ConsoleColor]::Red
        "Green" = [ConsoleColor]::Green
        "Yellow" = [ConsoleColor]::Yellow
        "Blue" = [ConsoleColor]::Blue
        "Cyan" = [ConsoleColor]::Cyan
        "Magenta" = [ConsoleColor]::Magenta
    }

    if ($ColorMap.ContainsKey($Color)) {
        Write-Host "[$Color] " -ForegroundColor $ColorMap[$Color] -NoNewline
    }
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-ColorOutput "INFO $Message" "Blue"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "SUCCESS $Message" "Green"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "WARNING $Message" "Yellow"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "ERROR $Message" "Red"
}

# 检查命令是否存在
function Test-Command {
    param([string]$Command)

    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

# 获取操作系统信息
function Get-OSInfo {
    return $PSVersionTable.Platform
}

# 主函数
function Invoke-Main {
    $osInfo = Get-OSInfo

    Write-Info "Noveris AI 开发环境初始化脚本"
    Write-Info "检测到的操作系统: $osInfo"
    Write-Host ""

    # 检查必要的工具
    Write-Info "检查必要的工具..."

    # 检查Git
    if (Test-Command "git") {
        try {
            $gitVersion = git --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $version = $gitVersion -replace '^git version ', ''
                Write-Success "Git 已安装: $version"
            } else {
                throw "Git command failed"
            }
        }
        catch {
            Write-Error "Git 安装检查失败"
            if (-not $SkipChecks) { exit 1 }
        }
    }
    else {
        Write-Error "请安装 Git: https://git-scm.com/"
        if (-not $SkipChecks) { exit 1 }
    }

    # 检查Docker
    if (Test-Command "docker") {
        try {
            $dockerVersion = docker --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $version = ($dockerVersion -split ' ')[2] -replace ',', ''
                Write-Success "Docker 已安装: $version"
            }
        }
        catch {
            Write-Error "Docker 版本检查失败"
        }

        # 检查Docker Compose
        if (Test-Command "docker-compose") {
            try {
                $composeVersion = docker-compose --version 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $version = ($composeVersion -split ' ')[2]
                    Write-Success "Docker Compose 已安装: $version"
                }
            }
            catch {
                Write-Error "Docker Compose 版本检查失败"
            }
        }
        else {
            Write-Error "Docker Compose 未找到"
            if (-not $SkipChecks) { exit 1 }
        }
    }
    else {
        Write-Error "请安装 Docker: https://docs.docker.com/get-docker/"
        if (-not $SkipChecks) { exit 1 }
    }

    # 检查Python
    $pythonCommands = @("python3", "python")
    $pythonFound = $false

    foreach ($cmd in $pythonCommands) {
        if (Test-Command $cmd) {
            try {
                $pythonVersion = & $cmd --version 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $version = ($pythonVersion -split ' ')[1]
                    if ($version -match '^3\.') {
                        Write-Success "$cmd 已安装: $version"
                        $pythonFound = $true
                        break
                    }
                    else {
                        Write-Warning "$cmd 版本过低: $version，建议升级到 Python 3.11+"
                    }
                }
            }
            catch {
                continue
            }
        }
    }

    if (-not $pythonFound) {
        Write-Warning "Python 未找到，后端开发需要 Python 3.11+"
    }

    # 检查Node.js
    if (Test-Command "node") {
        try {
            $nodeVersion = node --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Node.js 已安装: $nodeVersion"
            }
        }
        catch {
            Write-Error "Node.js 版本检查失败"
        }

        if (Test-Command "npm") {
            try {
                $npmVersion = npm --version 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "npm 已安装: $npmVersion"
                }
            }
            catch {
                Write-Error "npm 版本检查失败"
            }
        }
        else {
            Write-Error "npm 未找到"
            if (-not $SkipChecks) { exit 1 }
        }
    }
    else {
        Write-Warning "Node.js 未找到，前端开发需要 Node.js 18+"
    }

    Write-Host ""
    Write-Info "环境检查完成，开始初始化项目..."

    # 创建必要的目录
    Write-Info "创建项目目录结构..."
    $directories = @(
        "Backend",
        "Frontend",
        "Deploy/Postgres",
        "Deploy/Redis",
        "Deploy/Minio",
        "Deploy/Elastic",
        "Deploy/Build",
        "Scripts/bootstrap",
        "Scripts/db",
        "Scripts/ci",
        "Scripts/ops",
        "Docs"
    )

    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    Write-Success "项目目录结构已创建"

    # 复制环境变量模板
    if (Test-Path "env-example-template.txt") {
        if (-not (Test-Path ".env") -or $Force) {
            Copy-Item "env-example-template.txt" ".env"
            Write-Success "已创建 .env 文件，请根据需要修改配置"
        }
        else {
            Write-Warning ".env 文件已存在，跳过创建 (使用 -Force 强制覆盖)"
        }
    }
    else {
        Write-Warning "env-example-template.txt 文件不存在"
    }

    # 创建.gitignore（如果不存在）
    if (-not (Test-Path ".gitignore") -or $Force) {
        $gitignoreContent = @'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Docker
.docker/

# Temporary files
tmp/
temp/
'@

        Set-Content -Path ".gitignore" -Value $gitignoreContent
        Write-Success "已创建 .gitignore 文件"
    }

    Write-Host ""
    Write-Success "项目初始化完成！"
    Write-Host ""
    Write-Info "接下来你可以："
    Write-Host "  1. 修改 .env 文件中的配置"
    Write-Host "  2. 运行开发环境启动脚本"
    Write-Host "  3. 查看 Docs/ 目录中的规范文档"
    Write-Host "  4. 运行 Scripts/bootstrap/setup-dev.ps1 进行开发环境设置"
    Write-Host ""
    Write-Info "如需帮助，请查看 README.md 或 Docs/00-INDEX.md"
}

# 执行主函数
Invoke-Main
