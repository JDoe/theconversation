from mongoengine import *

class User(EmbeddedDocument):
    id_str = StringField(required=True)
    auth_type = StringField(required=True)
    username = StringField(required=True)
    fullname = StringField(required=True)
    screen_name = StringField(required=True)
    profile_image_url_https = StringField(required=True)
    profile_image_url = StringField(required=True)

class VotedUser(EmbeddedDocument):
    id = StringField(required=True, primary_key=True)

class AccessToken(EmbeddedDocument):
    secret = StringField(required=True)
    user_id = StringField(required=True)
    screen_name = StringField(required=True)
    key = StringField(required=True)

class UserInfo(Document):
    meta = {
        'indexes': ['user.id_str']
    }
    user = EmbeddedDocumentField(User, required=True)
    access_token = EmbeddedDocumentField(AccessToken, required=True)
