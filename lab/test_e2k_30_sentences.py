# -*- coding: utf-8 -*-
"""Тест e2k транслитерации на 30 предложениях с латиницей, цифрами и катаканой."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from kana_reading import latin2kana, kanaize

TEST_SENTENCES = [
    # --- только латиница и цифры ---
    "3Dモデル",
    "2D図面",
    "4Kテレビ",
    "Wi-Fiルーター",
    "USBメモリ",
    "IT企業",
    "AI技術",
    "IEC規格",
    "CPUクーラー",
    "GPUサーバー",
    # --- смесь 일본ского + английского ---
    "社内LAN設定",
    "VPN接続",
    "HTMLコード",
    "CSSスタイル",
    "APIエンドポイント",
    "SDKドキュメント",
    "DX推進",
    "BIM/CIMモデル",
    "PLATEAUデータ",
    # --- длинные предложения с números ---
    "社員100名が3Dプリンターを使う",
    "2階建てオフィス",
    "第3四半期の売上",
    "Wi-Fiパスワードはabc123です",
    "Bluetooth 5.0対応",
    "HDDからSSDへ換装",
    "LTEエリア外",
    "4WD車",
    "2WAYバッグ",
    "USB-Cケーブル",
    "100%コットン",
    "ステータスコード200",
]

def main():
    from kana_reading import en_translit
    print("e2k доступен:", en_translit is not None and en_translit.has_e2k())
    print("=" * 70)
    fails = 0
    for i, src in enumerate(TEST_SENTENCES, 1):
        try:
            res = latin2kana(src)
            # kanaize полный (если g2p доступен)
            try:
                full = kanaize(src)
            except Exception:
                full = "(g2p недоступен)"
            print(f"{i:2}. {src:40s} -> {res}")
            if full != "(g2p недоступен)":
                print(f"    kanaize: {full}")
        except Exception as e:
            fails += 1
            print(f"{i:2}. {src:40s} -> ОШИБКА: {e}")
    print("=" * 70)
    print(f"Всего: {len(TEST_SENTENCES)}, ошибок: {fails}")

if __name__ == "__main__":
    main()
