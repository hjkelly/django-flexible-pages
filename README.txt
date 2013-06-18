Run your own demo:

Optional Steps (for cleanliness):
    sudo easy_install pip
    sudo pip install virtualenv
    sudo pip install virtualenvwrapper
    source /usr/local/bin/virtualenvwrapper.sh  # For simplicity; there are better ways for the long-term.
    mkvirtualenv flexible_pages_demo

Necessary steps:
    git clone https://github.com/hjkelly/django-flexible-pages.git
    cd django-flexible-pages
    pip install -r requirements.txt  # May require `sudo`, if you aren't in a virtualenv.
    python manage.py runserver
    Go to http://localhost:8000/ to see the page.
    Go to http://localhost:8000/admin/pages/page/1/ to see its admin view (username and password are both 'test').
