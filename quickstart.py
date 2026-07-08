#!/usr/bin/env python3
"""
Quick Start Script for SearchProductAgent

Cài đặt dependencies và chạy ứng dụng
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Chạy lệnh và hiển thị trạng thái"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"Lệnh: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n❌ Lệnh thất bại: {description}")
        sys.exit(1)
    print(f"\n✅ Thành công: {description}")

def main():
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║          🔍 SearchProductAgent - Quick Start 🔍           ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Check environment
    print("\n📋 Kiểm tra môi trường...")
    if not os.path.exists(".env"):
        print("⚠️  File .env không tìm thấy!")
        print("   Hãy sao chép từ .env.example hoặc tạo file .env với các biến cần thiết")
        print("   Biến bắt buộc:")
        print("   - OPENAI_BASE_URL (mặc định: http://localhost:11434/v1)")
        print("   - OPENAI_API_KEY (mặc định: ollama)")
        print("   - LOCAL_MODEL (ví dụ: llama3.1:8b)")
    
    # Check Python version
    if sys.version_info < (3, 10):
        print(f"❌ Python 3.10+ yêu cầu, nhưng bạn có {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Install dependencies
    run_command(
        f"{sys.executable} -m pip install -r requirements.txt --quiet",
        "Cài đặt dependencies"
    )
    
    # Check Ollama
    try:
        result = subprocess.run(
            "curl -s http://localhost:11434/api/tags",
            shell=True,
            capture_output=True,
            timeout=2
        )
        if result.returncode == 0:
            print("✅ Ollama server đang chạy")
        else:
            print("⚠️  Ollama server không phản hồi")
            print("   Khởi động Ollama: ollama serve")
    except:
        print("⚠️  Không thể kết nối Ollama")
        print("   Khởi động Ollama: ollama serve")
    
    print("\n" + "="*60)
    print("🚀 Chọn chế độ chạy:")
    print("="*60)
    print("1. 🌐 Web UI (Streamlit) - RECOMMENDED")
    print("   streamlit run streamlit_app.py")
    print("\n2. 💬 CLI Mode (Terminal)")
    print("   python main.py")
    print("\n" + "="*60)
    
    choice = input("\nNhập lựa chọn (1 hoặc 2) [mặc định 1]: ").strip() or "1"
    
    if choice == "1":
        print("\n🌐 Khởi động Streamlit UI...")
        run_command(
            f"{sys.executable} -m streamlit run streamlit_app.py",
            "Khởi động Streamlit"
        )
    elif choice == "2":
        print("\n💬 Khởi động CLI Mode...")
        run_command(
            f"{sys.executable} main.py",
            "Khởi động Agent"
        )
    else:
        print("❌ Lựa chọn không hợp lệ")
        sys.exit(1)

if __name__ == "__main__":
    main()
