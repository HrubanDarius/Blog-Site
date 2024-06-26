from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash,request #request l-am luat pt contact
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar# PT COMMENTS
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps# PT DECORATOR
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CommentForm, CreatePostForm, LoginForm, RegisterForm
import smtplib
import os
#REQUIRE 5 ENV VAR EXPORTS


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

#PT AVATARE LA COMENTARII
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///blog.db") #If the "DB_URI" environment variable is not set, it defaults to "sqlite:///blog.db".
db = SQLAlchemy(model_class=Base)
db.init_app(app)


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))#face referinta la id din user
    author = relationship("User", back_populates="posts")#stabileste prima relatie intre POST-USER

    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    
    #***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")#reverse relation

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

    posts = relationship("BlogPost", back_populates="author")#reverse relation, USER-POST

    comments = relationship("Comment", back_populates="comment_author")#reverse relation


class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))#face referinta la id din user
    comment_author = relationship("User", back_populates="comments")
    
    #***************Child Relationship*************#
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("blog_posts.id"))#face referinta la id din post
    parent_post = relationship("BlogPost", back_populates="comments")
    



#------------------AUTHENTIFICATION--------------------
# Configure Flask-Login's Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

# Create a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)
#-------------------------------------------------------


with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit() == True:

        result = db.session.execute(db.select(User).where(User.email == register_form.email.data))
        user = result.scalar()
        if user:  #daca user are o valoare thrutfull (daca exista)
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=register_form.email.data,
            password=hash_and_salted_password,
            name=register_form.name.data,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)#login
        return redirect(url_for("get_all_posts"))
    
    return render_template("register.html", form = register_form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit() == True:

        result = db.session.execute(db.select(User).where(User.email == login_form.email.data))
        user = result.scalar()
        # Email doesn't exist or password incorrect.
        if not user:
            flash("That email does not exist, please try again.")#MESAJ DE EROARE, APARE 1 DATA SI DUPA REFRESH DISPARE
            return redirect(url_for('login'))
        elif check_password_hash(user.password, login_form.password.data) == False:
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form = login_form)


@app.route('/logout')
def logout():
    logout_user()#logout
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)



# TODO: Allow logged-in users to comment on posts
# Add a POST method to be able to post comments
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    # Add the CommentForm to the route
    comment_form = CommentForm()
    # Only allow logged-in users to comment on posts
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user, #reverse atribut -?AM ASOCIAT COMENTARIUL CU USER  ->  ACCESEZI IN post.html cu post.comments.comment_author.name,  post.comments(imi sare din BlogPost in Comment)   ,    post.comments.comment_author(imi sare in User),   post.comments.comment_author.name(imi sare in name din User)
            parent_post=requested_post   #reverse atribut -> AM ASOCIAT COMENTARIUL CU BLOGPOST  -> ACCESEZI in post.html  cu post.author.name (post.author, sare in BlogPost si .name sare in User name)
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, current_user=current_user, form=comment_form)



# TODO: Use a decorator so only an admin user can create a new post

#abort(403) iti da redirect pe alta pagina cu codul de eroare

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)        
    return decorated_function


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")




my_email = os.environ.get('MY_EMAIL')
sending_email = os.environ.get('SENDING_EMAIL')
my_password = os.environ.get('SENDING_EMAIL_PASSWORD')

@app.route('/contact', methods=['POST', 'GET'])
def contact():
    if request.method == 'POST':
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        #SENDING EMAIL....
        try:
            with smtplib.SMTP("smtp.gmail.com") as connection:
                connection.starttls()#encryptare mesaj sa fie sigur
                connection.login(user=my_email, password=my_password)
                connection.sendmail(from_addr=my_email, to_addrs=sending_email, msg=f"Subject:Blog Message from {name}!\n\n{message}\nemail: {email}\nphone: {phone}")
                print("Email trimis cu succes!")
                return render_template("contact.html", msg_sent = True)
        except:
            print("Email-ul nu s-a trimis cu succes.")
            return render_template("contact.html", msg_sent = False)#VARIABILA CREATA PT TITLU IN CONTACT CU {% if %}
    
    else:
        return render_template("contact.html", msg_sent = False)


if __name__ == "__main__":
    app.run(debug=False)
