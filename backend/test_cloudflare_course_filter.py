import asyncio
from unittest.mock import AsyncMock, patch

from providers.cloudflare import CloudflareVectorDBProvider


class FakeResponse:
    is_success = True

    def json(self):
        return {
            "result": {
                "matches": [
                    {
                        "score": 0.95,
                        "metadata": {
                            "course_id": "course-1",
                            "document_id": "doc-1",
                            "filename": "pdf-a.pdf",
                            "page_number": 2,
                            "text": "Relevant course content"
                        }
                    },
                    {
                        "score": 0.81,
                        "metadata": {
                            "course_id": "course-2",
                            "document_id": "doc-2",
                            "filename": "pdf-b.pdf",
                            "page_number": 7,
                            "text": "Unrelated content"
                        }
                    }
                ]
            }
        }


async def _run_test():
    provider = CloudflareVectorDBProvider()
    fake_client = AsyncMock()
    fake_client.post.return_value = FakeResponse()

    with patch("providers.cloudflare._get_shared_async_client", return_value=fake_client):
        results = await provider.search(course_id="course-1", query_vector=[0.1, 0.2], limit=10)

    assert len(results) == 1, f"Expected one matching course result, got {results}"
    assert results[0]["course_id"] == "course-1"
    assert "Unrelated content" not in results[0].get("text", "")


def test_cloudflare_course_filtering():
    asyncio.run(_run_test())
