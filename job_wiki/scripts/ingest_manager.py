import os
from datetime import datetime


def sanitize_filename(filename):
    # 공백 제거 및 소문자화, 날짜 접두어 추가
    clean_name = filename.replace(" ", "_").lower()
    if not clean_name.startswith(datetime.now().strftime("%Y%m%d")):
        clean_name = f"{datetime.now().strftime('%Y%m%d')}_{clean_name}"
    return clean_name


def organize_raw_files():
    raw_path = "00_Raw/"
    processed_path = "00_Raw/processed/"
    
    if not os.path.exists(processed_path):
        os.makedirs(processed_path)

    for file in os.listdir(raw_path):
        if file.endswith(".md") and not file.startswith("README"):
            # 1. 파일명 표준화
            new_name = sanitize_filename(file)
            src = os.path.join(raw_path, file)
            dest = os.path.join(raw_path, new_name)
            
            try:
                os.rename(src, dest)
                print(f"✅ Standardized: {file} -> {new_name}")
            except Exception as e:
                print(f"⚠️ Failed to rename {file}: {e}")
                continue
            
            # 2. 에이전트에게 알림 (이후 에이전트가 wiki 생성 후 processed로 이동하도록 유도)
            print(f"🚀 Ready for Synthesis: {new_name}")


if __name__ == "__main__":
    organize_raw_files()
