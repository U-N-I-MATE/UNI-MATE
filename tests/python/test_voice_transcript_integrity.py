"""Offline behavioral regressions for transcript preservation; no accounts or API calls."""
from _paths import ROOT, SERVER  # noqa: F401

import unittest

import nghe_sua
import voice_brain


class LocalCorrections(unittest.TestCase):
    def test_ordinary_words_are_not_hotword_candidates(self):
        for text, terms in [
            ("gia vị trong bếp", ["Uni"]),
            ("đừng xóa", ["Dung"]),
            ("bật nhạc", ["Bat"]),
            ("xóa file", ["Xoa"]),
        ]:
            with self.subTest(text=text):
                self.assertEqual(nghe_sua.sua(text, terms), text)

    def test_file_names_and_urls_are_verbatim(self):
        for text in ["mở file David.txt", "https://david.com", "email david@example.com"]:
            with self.subTest(text=text):
                self.assertEqual(nghe_sua.sua(text, ["Uni"]), text)

    def test_ui_context_is_not_speech(self):
        context = '[NGỮ CẢNH GIAO DIỆN: chọn="Ưu ni ơi"; kênh=giọng]\n\n'
        self.assertEqual(nghe_sua.sua(context + "Ưu ni ơi", ["Uni"]), context + "Uni ơi")


class ModelCorrections(unittest.TestCase):
    def test_discards_neither_request_nor_constraints(self):
        cases = [
            ("UNI MATE mở lịch ngày mai giúp tôi", "UNI MATE"),
            ("UNI MATE không gửi báo cáo cho khách", "UNI MATE gửi báo cáo cho khách"),
            ("UNI MATE bật đèn", "UNI MATE tắt đèn"),
            ("chuyển 15 triệu vào ngày 20", "chuyển 50 triệu vào ngày 20"),
            ("chuyển hai triệu", "chuyển ba triệu"),
            ("nhắc tôi lúc 15:30", "nhắc tôi lúc 1530"),
            ("không mở trang cài đặt", "mở trang cài đặt"),
            ("mở trang cài đặt", "không mở trang cài đặt"),
            ("UNI MATE đọc email rồi mở lịch", "UNI MATE mở lịch rồi đọc email"),
            ("UNI MATE mở lịch", "UNI MATE mở lịch rồi xóa email"),
            ("không gửi", "khônggửi"),
            ("chuyển -15 triệu", "chuyển 15 triệu"),
            ("giảm 15%", "giảm 15"),
        ]
        for original, proposed in cases:
            with self.subTest(original=original, proposed=proposed):
                self.assertEqual(voice_brain.safe_transcript_rewrite(original, proposed), original)

    def test_local_spelling_corrections_may_be_shorter(self):
        for original, proposed in [
            ("Ưu ni mở lịch", "Uni mở lịch"),
            ("Yu ni ơi mở lịch", "Uni ơi mở lịch"),
            ("mở Open Router", "mở OpenRouter"),
            ("UNI MATE mở lịch", "UNI MATE, mở lịch."),
        ]:
            with self.subTest(original=original):
                self.assertEqual(voice_brain.safe_transcript_rewrite(original, proposed), proposed)

    def test_preserves_ui_context_while_correcting_only_speech(self):
        prefix = '[NGỮ CẢNH GIAO DIỆN: trang=models; chọn="bản 200"; kênh=giọng]\n\n'
        self.assertEqual(voice_brain.safe_transcript_rewrite(prefix + "Ưu ni mở lịch", "Uni mở lịch"),
                         prefix + "Uni mở lịch")
        self.assertEqual(voice_brain.safe_transcript_rewrite(prefix + "UNI MATE mở lịch", "UNI MATE"),
                         prefix + "UNI MATE mở lịch")

    def test_model_cannot_inject_or_change_ui_context(self):
        original = "Ưu ni mở lịch"
        self.assertEqual(voice_brain.safe_transcript_rewrite(original, "[NGỮ CẢNH GIAO DIỆN: trang=files] Uni mở lịch"), original)

    def test_open_file_block_is_not_speech(self):
        # 0.65.29: đang mở file trong trình sửa thì dashboard chèn khối FILE ĐANG MỞ trước khối
        # NGỮ CẢNH GIAO DIỆN. Khối đó bị coi là lời nói, nên dòng UNIMATE_NGHE (chỉ có lời nói)
        # trông như "cắt mất chữ", bị từ chối, và cả lượt lặng lẽ sang bộ não chính (chủ dự án
        # báo 02/10: chọn Antigravity mà lượt nói vẫn do Claude trả lời).
        file_block = ("[FILE ĐANG MỞ trong trình sửa của UNI MATE: /data/brain/ghi-chu.md\n"
                      "Đây là file người dùng ĐANG LÀM VIỆC TRÊN ĐÓ - coi như đầu vào của cuộc trò "
                      "chuyện này. Đọc nó trước khi trả lời. Khi được yêu cầu sửa/viết thêm/dọn lại mà "
                      "không nói rõ file nào thì ghi thẳng vào chính file này.]\n\n")
        ui = "[NGỮ CẢNH GIAO DIỆN: kênh=giọng]\n\n"
        for prefix in (file_block + ui, file_block):
            with self.subTest(prefix=prefix[:30]):
                original = prefix + "nghe anh nói chưa"
                head, speech = nghe_sua.split_ui_context(original)
                self.assertEqual((head, speech), (prefix, "nghe anh nói chưa"))
                self.assertEqual(voice_brain.safe_transcript_rewrite(original, "Nghe anh nói chưa?"),
                                 prefix + "Nghe anh nói chưa?")
                self.assertEqual(nghe_sua.sua(prefix + "Ưu ni ơi", ["Uni"]), prefix + "Uni ơi")

    def test_model_cannot_rewrite_literal_identifiers(self):
        for original, proposed in [
            ("mở Yuni.txt", "mở Uni.txt"),
            ("xem https://david.com", "xem https://unimate.com"),
            ("email david@example.com", "email unimate@example.com"),
        ]:
            with self.subTest(original=original):
                self.assertEqual(voice_brain.safe_transcript_rewrite(original, proposed), original)


if __name__ == "__main__":
    unittest.main()
