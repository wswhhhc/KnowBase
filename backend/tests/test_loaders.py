import unittest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from src.rag.loaders import (
    load_document, load_url, _is_private_url, _is_safe_ip,
)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _write(self, name: str, content: str) -> str:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    # ── 文件加载 ──

    def test_load_txt(self):
        path = self._write("test.txt", "你好世界")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "你好世界")
        self.assertEqual(docs[0].metadata["source"], "test.txt")

    def test_load_md(self):
        path = self._write("test.md", "# Title\n\nContent.")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Content", docs[0].page_content)

    def test_load_pdf_returns_pages(self):
        from pypdf import PdfWriter
        pdf_path = str(self.tmp / "test.pdf")
        writer = PdfWriter()
        writer.add_blank_page(72, 72)
        writer.add_metadata({"/Title": "Test Page"})
        writer.write(pdf_path)
        docs = load_document(pdf_path)
        self.assertGreaterEqual(len(docs), 1)
        for doc in docs:
            self.assertIn("page", doc.metadata)

    def test_load_docx(self):
        from docx import Document as DocxDocument
        docx_path = str(self.tmp / "test.docx")
        doc = DocxDocument()
        doc.add_paragraph("Hello from docx.")
        doc.save(docx_path)
        docs = load_document(docx_path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Hello from docx", docs[0].page_content)
        self.assertEqual(docs[0].metadata["source"], "test.docx")

    def test_load_html(self):
        path = self._write("test.html", "<html><body><h1>Title</h1><p>Content.</p></body></html>")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Title", docs[0].page_content)
        self.assertIn("Content", docs[0].page_content)

    def test_load_html_strips_script_style(self):
        path = self._write("test.html", "<html><body><script>alert(1)</script><style>.c{}</style><p>Real.</p></body></html>")
        docs = load_document(path)
        self.assertNotIn("alert", docs[0].page_content)
        self.assertIn("Real", docs[0].page_content)

    def test_load_unsupported_extension_raises(self):
        with self.assertRaises(ValueError):
            load_document(str(self.tmp / "data.xyz"))

    def test_source_name_overrides_file_path_name(self):
        path = self._write("actual.txt", "data")
        docs = load_document(path, source_name="custom.txt")
        self.assertEqual(docs[0].metadata["source"], "custom.txt")

    def test_load_htm_as_html(self):
        path = self._write("page.htm", "<html><p>Hello</p></html>")
        docs = load_document(path)
        self.assertEqual(len(docs), 1)
        self.assertIn("Hello", docs[0].page_content)

    # ── _is_safe_ip ──

    def test_safe_ip_rejects_unspecified(self):
        import ipaddress
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("0.0.0.0")))

    def test_safe_ip_rejects_private(self):
        import ipaddress
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("10.0.0.1")))
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("192.168.1.1")))

    def test_safe_ip_rejects_cgnat(self):
        """100.64.0.0/10（运营商级 NAT）→ is_global=False → 不通过"""
        import ipaddress
        net = ipaddress.ip_network("100.64.0.0/10")
        for addr in list(net.subnets(new_prefix=24))[:3]:
            self.assertFalse(_is_safe_ip(next(addr.hosts())))

    def test_safe_ip_rejects_loopback(self):
        import ipaddress
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("127.0.0.1")))

    def test_safe_ip_rejects_link_local(self):
        import ipaddress
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("169.254.1.1")))

    def test_safe_ip_rejects_multicast(self):
        import ipaddress
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("224.0.0.1")))

    def test_safe_ip_rejects_reserved(self):
        import ipaddress
        # 240.0.0.1 属于 reserved
        self.assertFalse(_is_safe_ip(ipaddress.ip_address("240.0.0.1")))

    def test_safe_ip_accepts_public(self):
        import ipaddress
        self.assertTrue(_is_safe_ip(ipaddress.ip_address("1.1.1.1")))
        self.assertTrue(_is_safe_ip(ipaddress.ip_address("8.8.8.8")))

    # ── _is_private_url ──

    def test_ssrf_ipv4_private(self):
        self.assertTrue(_is_private_url("http://10.0.0.1"))
        self.assertTrue(_is_private_url("http://172.16.0.1"))
        self.assertTrue(_is_private_url("http://192.168.1.1"))

    def test_ssrf_loopback(self):
        self.assertTrue(_is_private_url("http://127.0.0.1:8080/api"))
        self.assertTrue(_is_private_url("http://[::1]:8000"))

    def test_ssrf_link_local(self):
        self.assertTrue(_is_private_url("http://169.254.169.254/latest/meta-data"))

    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 0))])
    def test_ssrf_public_domain_is_public(self, mock_addrinfo):
        self.assertFalse(_is_private_url("http://www.baidu.com/s?wd=test"))

    # ── load_url 功能测试（mock Session 绕过网络）──

    def _make_ok_response(self, text: str):
        import requests as req
        r = Mock(status_code=200)
        r.text = text
        r.apparent_encoding = "utf-8"
        r.raise_for_status = Mock()
        r.headers = req.structures.CaseInsensitiveDict({"Content-Type": "text/html"})
        return r

    @patch("requests.Session")
    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 0))])
    def test_load_url_parses_content(self, mock_addrinfo, mock_session_cls):
        """正文提取、导航去除、title 识别"""
        mock_session = Mock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = self._make_ok_response(
            "<html><head><title>示例文章</title></head>"
            "<body><nav>导航</nav><main><h1>标题</h1><p>正文内容</p></main></body></html>"
        )
        docs = load_url("https://example.com/article")
        self.assertEqual(len(docs), 1)
        self.assertIn("标题", docs[0].page_content)
        self.assertIn("正文内容", docs[0].page_content)
        self.assertNotIn("导航", docs[0].page_content)
        self.assertEqual(docs[0].metadata["source"], "https://example.com/article")
        self.assertEqual(docs[0].metadata["title"], "示例文章")

    @patch("requests.Session")
    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.2.3.4", 0))])
    def test_load_url_respects_source_name(self, mock_addrinfo, mock_session_cls):
        """source_name 覆盖 metadata.source"""
        mock_session = Mock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = self._make_ok_response("<html><body><p>content</p></body></html>")
        docs = load_url("https://example.com", source_name="custom")
        self.assertEqual(docs[0].metadata["source"], "custom")

    @patch("requests.Session")
    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.2.3.4", 0))])
    def test_load_url_rejects_empty_content(self, mock_addrinfo, mock_session_cls):
        """空正文 → ValueError"""
        mock_session = Mock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = self._make_ok_response("<html><head><title>Empty</title></head><body></body></html>")
        with self.assertRaisesRegex(ValueError, "未提取到正文"):
            load_url("https://example.com/empty")

    @patch("requests.Session")
    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.2.3.4", 0))])
    def test_load_url_rejects_login_redirect(self, mock_addrinfo, mock_session_cls):
        """抓取到登录页 → ValueError"""
        mock_session = Mock()
        mock_session_cls.return_value.__enter__.return_value = mock_session

        # 第一次请求：302 → 飞书登录页
        login_url = "https://accounts.feishu.cn/accounts/page/login?redirect_uri=xxx"
        redir = Mock(status_code=302, headers={"Location": login_url})
        redir.raise_for_status = Mock()
        mock_session.get.side_effect = [
            redir,  # 第一次请求返回 302
            self._make_ok_response("<html><body>login page</body></html>"),  # 第二次获取登录页
        ]

        with self.assertRaisesRegex(ValueError, "登录"):
            load_url("https://example.com/wiki/abc")

    @patch("requests.Session")
    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.2.3.4", 0))])
    def test_load_url_https_works_end_to_end_mocked(self, mock_addrinfo, mock_session_cls):
        """验证 HTTPS URL 请求通过 mocked Session 返回正确结果"""
        mock_session = Mock()
        mock_session_cls.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = self._make_ok_response("<html><body><p>ok</p></body></html>")
        docs = load_url("https://example.com/page")
        self.assertEqual(docs[0].metadata["url"], "https://example.com/page")

    # ── SSRF 拒绝测试 ──

    def test_ssrf_rejects_private_ip(self):
        with self.assertRaisesRegex(ValueError, "内网"):
            load_url("http://127.0.0.1:8000/secret")

    @patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 0))])
    def test_ssrf_rejects_private_dns(self, mock_addrinfo):
        with self.assertRaisesRegex(ValueError, "内网"):
            load_url("http://internal.example.com/secret")

    # ── 真实 HTTPS 请求（集成 test）──

    def test_load_url_real_https(self):
        """真实请求 https://example.com 验证 TLS 握手正常"""
        docs = load_url("https://example.com")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["title"], "Example Domain")

    # ── _make_pinned_connection_cls 单元测试 ──

    @patch("urllib3.util.connection.create_connection")
    def test_pinned_connection_new_conn_uses_keyword_args(self, mock_create):
        """_new_conn() 用关键字参数调用 create_connection"""
        from src.rag.loaders import _make_pinned_connection_cls
        from urllib3.connection import HTTPConnection

        Cls = _make_pinned_connection_cls(HTTPConnection, "203.0.113.10")
        conn = Cls("www.example.com", 80)
        conn._new_conn()

        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args

        # 第一个位置参数是 address
        self.assertEqual(args[0], ("203.0.113.10", 80))

        # 其余必须都是关键字参数
        self.assertIn("timeout", kwargs)
        self.assertIn("source_address", kwargs)
        self.assertIn("socket_options", kwargs)



if __name__ == "__main__":
    unittest.main()
