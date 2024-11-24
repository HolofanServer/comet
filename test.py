import sys
import os
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv

from utils.logging import setup_logging

logger = setup_logging("D")

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client_ai = OpenAI(api_key=api_key)

def analyze_static_error_with_openai(error_message):
    logger.info("OpenAIにエラー内容を送信しています...")

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたは日本語で親切なPythonのコードアシスタントです。"},
                {
                    "role": "user",
                    "content": f"""
                    以下はPythonコードに対する静的解析エラーです。これを解決する提案を日本語で出してください。
                    また```markdownは追加しないでください。実際のコードレイ部分のみ```を使用してください
                    マークダウン形式で以下を含めてください:

                    1. 🚨 **エラーの概要**
                    2. 🛠️ **改善案**
                    3. 💡 **修正後のコード例**

                    エラー内容:  {error_message}
                    """
                }
            ]
        )
        suggestion = response.choices[0].message.content.strip()
        return suggestion
    except OpenAIError as e:
        logger.error(f"OpenAI API呼び出しに失敗しました: {e}")
        return None
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        return None

def read_error_file(file_path):
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        logger.error(f"エラーファイルの読み取りに失敗しました: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    error_file_path = sys.argv[1]
    error_message = read_error_file(error_file_path)

    if error_message:
        suggestion = analyze_static_error_with_openai(error_message)
        if suggestion:
            with open("openai_suggestions.md", "w") as f:
                f.write("# 🐍 静的解析エラーの修正提案\n\n")
                f.write(suggestion)
            logger.info("提案内容をファイルに保存しました。")
        else:
            logger.error("提案内容が取得できませんでした。")
    else:
        logger.error("エラーファイルが読み取れませんでした。")
