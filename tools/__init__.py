from tools.serpapi_discovery import search_serpapi
from tools.reddit_search import search_reddit
from tools.reddit_account import check_reddit_replies
from tools.reddit_posting import post_reddit_comment
from tools.github_stars import check_github_stars
from tools.github_repo import update_github_repo
from tools.gmail_tool import send_gmail

ALL_TOOLS = [
    search_serpapi,
    search_reddit,
    check_reddit_replies,
    post_reddit_comment,
    check_github_stars,
    update_github_repo,
    send_gmail,
]
