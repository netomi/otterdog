from flask_login import current_user, login_user
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.github import github, make_github_blueprint
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from sqlalchemy.orm.exc import NoResultFound
from .models import Users, db, OAuth


github_blueprint = make_github_blueprint(
    scope='user',
    storage=SQLAlchemyStorage(
        OAuth,
        db.session,
        user=current_user,
        user_required=False,
    ),
)


@oauth_authorized.connect_via(github_blueprint)
def github_logged_in(blueprint, token):
    info = github.get("/user")

    if info.ok:
        account_info = info.json()
        username = account_info["login"]
        email = account_info["email"]

        query = Users.query.filter_by(oauth_github=username)
        try:
            user = query.one()
            login_user(user)

        except NoResultFound:
            # Save to db
            user = Users()
            user.username = '(gh)' + username
            user.oauth_github = username
            user.email = email

            # Save current user
            db.session.add(user)
            db.session.commit()

            login_user(user)
