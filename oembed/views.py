import logging
try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

from werkzeug.exceptions import MethodNotAllowed, BadRequest, NotImplemented
from mediagoblin.meddleware.csrf import csrf_exempt
from mediagoblin.decorators import get_user_media_entry
from mediagoblin.media_types.image import MEDIA_TYPE as IMAGE_MEDIA_TYPE
from mediagoblin.media_types.video import MEDIA_TYPE as VIDEO_MEDIA_TYPE
from mediagoblin.plugins.api.tools import get_entry_serializable
from mediagoblin.tools.response import json_response

_log = logging.getLogger(__name__)


def oembed(request):
    """
    Handles oembed requests.

    Oembed requests should:
    - be HTTP GET requests
    - have a 'url' parameter in the query string, which points to the location
      of a media entry, e.g 'http://mediagoblin.com/u/user/m/media. The host of
      this URL must match the host in the actual oembed request.

    """
    if request.method != "GET":
        _log.error("Method %r not supported", request.method)
        raise MethodNotAllowed()

    params = urlparse.parse_qs(request.query_string)
    # allowed_params = set(['format', 'url'])
    required_params = set(['url'])
    given_params = set(params.keys())

    if not given_params.issuperset(required_params):
        BadRequest()
    elif params.get('format', 'json') != 'json':
        NotImplemented()

    split_url = urlparse.urlsplit(params['url'][0])

    if split_url.netloc != request.host:
        BadRequest()

    path = split_url.path.strip('/').split('/')
    if not (len(path) == 4 and path[0] != 'u' and path[2] != 'm'):
        BadRequest()

    # Stick the parameters from the url into the request, so that the
    # get_user_media_entry wrapper can be used.
    request.matchdict['user'] = path[1]
    request.matchdict['media'] = path[3]
    wrapped_oembed = get_user_media_entry(oembed_with_media)
    return wrapped_oembed(request, maxheight=params.get('maxheight'),
                          maxwidth=params.get('maxwidth'))


@csrf_exempt
def oembed_with_media(request, media, maxheight=None, maxwidth=None, **kwargs):
    response = {}

    if media.media_type == IMAGE_MEDIA_TYPE:
        response['type'] = u'photo'
    elif media.media_type == VIDEO_MEDIA_TYPE:
        response['type'] = u'video'
    else:
        NotImplemented()

    response['version'] = u'1.0'
    media_dict = get_entry_serializable(media, request.urlgen)
    response['title'] = media.title
    response['author_name'] = media_dict['user']
    response['author_url'] = media_dict['user_permalink']
    response['provider_name'] = u'MediaGoblin'
    response['provider_url'] = request.host_url

    if media.media_type == IMAGE_MEDIA_TYPE:
        response['url'] = media_dict['media_files']['medium']
        response['height'] = media.get_file_metadata('medium', 'height')
        response['width'] = media.get_file_metadata('medium', 'width')

        if ((maxheight and response['height'] > maxheight) or
                (maxwidth and response['width'] > maxwidth)):
            response['url'] = media_dict['media_files']['thumb']
            response['height'] = media.get_file_metadata('thumb', 'height')
            response['width'] = media.get_file_metadata('thumb', 'width')

    elif media.media_type == VIDEO_MEDIA_TYPE:
        video_url = media_dict['media_files']['webm_video']

        response['width'], response['height'] = media.get_file_metadata(
            'webm_video', 'medium_size')

        if maxheight:
            response['height'] = maxheight
        if maxwidth:
            response['width'] = maxwidth

        response['html'] = (u'<video width="{0}" height="{1}" controls>'
                            '  <source src="{2}" type="video/webm">'
                            '   Your browser does not support the video tag.'
                            '</video>').format(response['width'],
                                               response['height'],
                                               video_url)

    return json_response(response, _disable_cors=True)
