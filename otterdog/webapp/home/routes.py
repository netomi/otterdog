from flask import render_template, request
from flask_login import login_required  # type: ignore
from jinja2 import TemplateNotFound

from otterdog.webapp.home import blueprint


@blueprint.route('/')
@blueprint.route('/index')
@blueprint.route('/index.html')
@login_required
def index():
    from .models import Organizations

    orgs = Organizations.query.all()
    return render_template('home/index.html', organizations=orgs)


@blueprint.route('/organizations')
@login_required
def organizations():
    from .models import Organizations

    orgs = Organizations.query.all()
    return render_template('home/organizations.html', organizations=orgs)


@blueprint.route('/organizations/<org_id>')
@login_required
def org(org_id: str):
    from .models import Organizations

    org = Organizations.query.filter_by(github_id=org_id).first()
    return render_template('home/org.html', org=org)


@blueprint.route('/<template>')
@login_required
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):
    try:
        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except Exception:
        return None
