import os
from flask import Flask, request
from github import Github, GithubIntegration
from matplotlib.style import context

app = Flask(__name__)

app_id = 174822

# Read the bot certificate
with open(
        os.path.normpath(os.path.expanduser('bot_key.pem')),
        'r'
) as cert_file:
    app_key = cert_file.read()
    
# Create an GitHub integration instance
git_integration = GithubIntegration(
    app_id,
    app_key,
)

def pr_watch_title(repo, payload):
    title = payload['pull_request']['title']
    pr = repo.get_issue(number=payload['pull_request']['number'])

    commit_sha = repo.get_git_ref(f'heads/{payload["pull_request"]["head"]["ref"]}').object.sha
    print(f"Commit SHA: {commit_sha}")

    if any(w in title.lower() for w in ['wip', 'work in progress', 'do not merge']):
        # Add pending status
        repo.get_commit(sha=commit_sha).create_status(
            state='pending',
            context="umons-bot/WIP"
        )

    else:
        # Check if the pull request has a label called "pending"
        if repo.get_commit(sha=commit_sha).get_statuses(context="umons-bot/WIP").get_page(0)[0].state == "pending": # TODO try
            # Set the status to "success"
            repo.get_commit(sha=commit_sha).create_status(
                state='success',
                context="umons-bot/WIP"
            )   


def issue_created_event(repo, payload):
    """
    Note: This implementation is not complete. It does not handle the case where a contributor
    adds a WIP in the title AFTER a comment with `@umons-bot-tutorial ready for review`
    """
    comment: str = payload["comment"]["body"]
    print(f"Comment: {comment}")

    # Check if the issue was created in a pull request
    if "pull_request" in payload["issue"].keys():
        # Get the pull request and set the sucess satus
        pr = repo.get_issue(number=payload['issue']['number']).as_pull_request() # Every pull request is also an issue
        # get the latest commit in the PR

        lastest_commit_sha = pr.get_commits().get_page(0)[0].commit.sha

        print(lastest_commit_sha)

        # Look is the comment is a `ready for review` command for the bot
        if index := comment.find("@umons-bot-tutorial") >= 0:
            rest_of_comment = comment[index+len("@umons-bot-tutorial"):]
            print(f"Rest of comment: {rest_of_comment}")
            if "ready for review" in rest_of_comment.lower():
                # Add a success status to the pull request
                print("Adding a success status to the pull request")
                repo.get_commit(sha=lastest_commit_sha).create_status(
                    state='success',
                    context="umons-bot/WIP"
                )


            


def pr_opened_event(repo, payload):
    pr = repo.get_issue(number=payload['pull_request']['number'])
    author = pr.user.login

    is_first_pr = repo.get_issues(creator=author).totalCount

    if is_first_pr == 1:
        response = f"Thanks for opening this pull request, @{author}! " \
                   f"The repository maintainers will look into it ASAP! :speech_balloon:"
        pr.create_comment(f"{response}")
        pr.add_to_labels("needs review")
    
    pr_watch_title(repo, payload)


def pr_closed_event(repo, payload):
    pr = repo.get_issue(number=payload['pull_request']['number'])
    author = pr.user.login

    # Add a new comment
    pr.create_comment(f"Thanks for closing this pull request, @{author}! ")

    if payload['pull_request']['merged']:
        # Delete the branch
        pr.create_comment(f"This pull request was merged successfully! Deteting the branch.")
        repo.get_git_ref(f'heads/{payload["pull_request"]["head"]["ref"]}').delete()

    
def pr_edited_event(repo, payload):
    pr_watch_title(repo, payload)


@app.route("/", methods=['POST'])
def bot():
    payload = request.json

    if not 'repository' in payload.keys():
        return "", 204

    owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")

    # Check if the event is a GitHub pull request creation event
    if all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'opened':
        pr_opened_event(repo, payload)

    # Check if the event is a GitHub pull request closing event
    if all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'closed':
        pr_closed_event(repo, payload)

    if all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'edited':
        pr_edited_event(repo, payload)

    if all(k in payload.keys() for k in ['action', 'issue', 'comment']) and payload['action'] == 'created':
        issue_created_event(repo, payload)

    return "", 204

if __name__ == "__main__":
    app.run(debug=True, port=3000)
