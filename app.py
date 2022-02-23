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
        if not any(label.name == 'pending' for label in pr.labels): # TODO change commit.get_statuses().state == "pending"
            # Set the status to "success"
            repo.get_commit(sha=commit_sha).create_status(
                state='success',
                context="umons-bot/WIP"
            )   


def pr_watch_comment_status(repo, payload):
    comment: str = payload["comment"]["body"]

    pr = repo.get_issue(number=payload['pull_request']['number'])
    commit_sha = repo.get_git_ref(f'heads/{payload["pull_request"]["head"]["ref"]}').object.sha

    if index := comment.find("@umons-bot-tutorial") > 0:
        rest_of_comment = comment[index+len("@umons-bot-tutorial"):]
        print(f"Rest of comment: {rest_of_comment}")
        if "ready for review" in rest_of_comment.lower():
            # Add a label to the pull request
            pass # WIP

            


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

    if all(k in payload.keys() for k in ['action', 'issue_comment']) and payload['action'] == 'created':
        pr_watch_comment_status(repo, payload)

    return "", 204

if __name__ == "__main__":
    app.run(debug=True, port=3000)
