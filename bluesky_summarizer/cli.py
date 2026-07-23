import os
import sys
import argparse
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from bluesky_summarizer.agent import wrapped_agent
from bluesky_summarizer.bluesky_client import post_to_bluesky
from langfuse.decorators import observe


@observe(name="bluesky_summarizer_workflow")
def run_workflow(
    url: str,
    dry_run: bool = False,
    handle: Optional[str] = None,
    app_password: Optional[str] = None
) -> None:
    """
    Run the blog post reading, summarization, and Bluesky posting pipeline.
    """
    print("=" * 60)
    print(" 🚀 BLOG POST SUMMARIZER TO BLUESKY AGENT")
    print("=" * 60)
    print(f"📄 Target URL: {url}")
    print(f"⚙️ Mode: {'DRY RUN (Preview Only)' if dry_run else 'LIVE POSTING'}")
    print("-" * 60)

    # 1. Run Pydantic AI Agent to read & summarize blog post
    print("🤖 Agent fetching blog post and generating summary (<200 chars)...")
    prompt = f"Fetch and summarize the blog post at this URL in under 200 characters: {url}"

    try:
        result = wrapped_agent.run_sync(prompt)
        post_summary = result.output
    except Exception as e:
        print(f"\n❌ Error during agent execution: {e}")
        sys.exit(1)

    print("\n✅ Summary Generated Successfully!")
    print(f"📌 Original URL: {post_summary.url}")
    print(f"📝 Summary Text: {post_summary.summary}")
    print(f"📏 Character Count: {len(post_summary.summary)} / 200")

    if len(post_summary.summary) > 200:
        print("⚠️ Warning: Generated summary exceeds 200 characters!")
    else:
        print("✨ Length check PASSED (under 200 characters).")

    print("\n" + "-" * 60)
    print("📱 Formatting post for Bluesky...")
    
    # 2. Post to Bluesky (or dry run preview)
    bluesky_res = post_to_bluesky(
        summary_text=post_summary.summary,
        blog_url=url,
        handle=handle,
        app_password=app_password,
        dry_run=dry_run
    )

    print("\n--- BLUESKY POST PREVIEW ---")
    print(bluesky_res.get("post_text"))
    print("-" * 60)

    if bluesky_res.get("success"):
        if bluesky_res.get("dry_run"):
            print("💡 Dry run complete! Post was formatted successfully.")
            print("   To post live, set BSKY_HANDLE & BSKY_APP_PASSWORD in .env and omit --dry-run.")
        else:
            print(f"🎉 SUCCESS! {bluesky_res.get('message')}")
            if bluesky_res.get("uri"):
                print(f"🔗 Post URI: {bluesky_res.get('uri')}")
    else:
        print(f"❌ Failed to post to Bluesky: {bluesky_res.get('error')}")
        if not dry_run:
            print("💡 Tip: You can test with `--dry-run` to preview the output without credentials.")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Pydantic AI Agent: Read blog post, summarize in <200 chars, and post to Bluesky."
    )
    parser.add_argument(
        "url",
        nargs="?",
        type=str,
        help="The URL of the blog post to summarize and post."
    )
    parser.add_argument(
        "--url",
        "-u",
        dest="url_option",
        type=str,
        help="The URL of the blog post (alternative flag syntax)."
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="Run summarization and format Bluesky post preview without submitting to Bluesky API."
    )
    parser.add_argument(
        "--handle",
        type=str,
        help="Bluesky username/handle (overrides BSKY_HANDLE env var)."
    )
    parser.add_argument(
        "--app-password",
        type=str,
        help="Bluesky App Password (overrides BSKY_APP_PASSWORD env var)."
    )

    args = parser.parse_args()

    target_url = args.url or args.url_option

    if not target_url:
        print("=" * 60)
        print(" 🚀 BLOG POST SUMMARIZER TO BLUESKY AGENT")
        print("=" * 60)
        target_url = input("Enter Blog Post URL: ").strip()
        if not target_url:
            print("Error: No URL provided.")
            sys.exit(1)
        dry_run_input = input("Run in Dry-Run mode? (y/N): ").strip().lower()
        if dry_run_input in ['y', 'yes']:
            args.dry_run = True

    run_workflow(
        url=target_url,
        dry_run=args.dry_run,
        handle=args.handle,
        app_password=args.app_password
    )


if __name__ == "__main__":
    main()
