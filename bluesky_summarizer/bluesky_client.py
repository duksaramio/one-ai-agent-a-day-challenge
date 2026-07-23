import os
from typing import Dict, Any, Optional
from atproto import Client, client_utils


def post_to_bluesky(
    summary_text: str,
    blog_url: str,
    handle: Optional[str] = None,
    app_password: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Publish a post to Bluesky containing a summary (under 200 characters) and the original blog URL.

    Args:
        summary_text: The blog post summary (must be under 200 characters).
        blog_url: The original URL of the blog post.
        handle: Bluesky username/handle (e.g. user.bsky.social). Defaults to BSKY_HANDLE env var.
        app_password: Bluesky app password. Defaults to BSKY_APP_PASSWORD env var.
        dry_run: If True, formats the post payload without making active API calls.

    Returns:
        Dict containing success status, message, post preview, and post URI/CID if posted.
    """
    summary_text = summary_text.strip()
    if len(summary_text) > 200:
        raise ValueError(f"Summary exceeds maximum length of 200 characters (actual length: {len(summary_text)}).")

    # Build rich text with link facet
    tb = client_utils.TextBuilder()
    tb.text(summary_text)
    tb.text("\n\n🔗 Original Blog: ")
    tb.link(blog_url, blog_url)

    formatted_text = tb.build_text()
    
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": "Dry-run successful. Post was formatted but not submitted to Bluesky.",
            "summary_char_count": len(summary_text),
            "total_char_count": len(formatted_text),
            "post_text": formatted_text,
            "uri": None,
            "cid": None
        }

    # Resolve credentials
    effective_handle = handle or os.environ.get("BSKY_HANDLE")
    effective_password = app_password or os.environ.get("BSKY_APP_PASSWORD")

    if not effective_handle or not effective_password:
        return {
            "success": False,
            "dry_run": False,
            "error": "Missing Bluesky credentials. Please provide BSKY_HANDLE and BSKY_APP_PASSWORD via environment variables or CLI flags.",
            "summary_char_count": len(summary_text),
            "total_char_count": len(formatted_text),
            "post_text": formatted_text,
            "uri": None,
            "cid": None
        }

    try:
        client = Client()
        client.login(effective_handle, effective_password)
        response = client.send_post(tb)
        return {
            "success": True,
            "dry_run": False,
            "message": f"Successfully posted to Bluesky account @{effective_handle}!",
            "summary_char_count": len(summary_text),
            "total_char_count": len(formatted_text),
            "post_text": formatted_text,
            "uri": response.uri,
            "cid": response.cid
        }
    except Exception as e:
        return {
            "success": False,
            "dry_run": False,
            "error": f"Failed to post to Bluesky API: {str(e)}",
            "summary_char_count": len(summary_text),
            "total_char_count": len(formatted_text),
            "post_text": formatted_text,
            "uri": None,
            "cid": None
        }
