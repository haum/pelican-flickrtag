# -*- coding: utf-8 -*-
"""
Embed Flickr Images in Pelican Articles
=======================================

"""
import logging
import pickle
import re

import flickr as api_client

from pelican import signals

flickr_regex = re.compile(r'(\[flickr:id\=([0-9]+)\])')
default_template = """<span class="caption-container">
    <a class="caption" href="{{url}}" target="_blank">
        <img src="{{raw_url}}"
            alt="{{title}}"
            title="{{title}}"
            class="img-polaroid"
            {% if FLICKR_TAG_INCLUDE_DIMENSIONS %}
                width="{{width}}"
                height="{{height}}"
            {% endif %} />
    </a>
    <span class="caption-text muted">{{title}}</span>
</spam>"""

logger = logging.getLogger(__name__)


def setup_flickr(generator):
    """Add Flickr api object to Pelican settings."""

    for key in ('TOKEN', 'KEY', 'SECRET'):
        try:
            value = generator.settings['FLICKR_API_' + key]
            setattr(api_client, 'API_' + key, value)
        except KeyError:
            logger.warning('[flickrtag]: FLICKR_API_%s is not defined in the configuration' % key)

    generator.flickr_api_client = api_client
    try:
        place_holder_pict = generator.settings['FLICKR_TAG_PLACE_HOLDER_PICT']
    except:
        logger.error ('[flickrtag]: FLICKR_TAG_PLACE_HOLDER_PICT variable is mandatory in your config')

    try:
        place_holder_link = generator.settings['FLICKR_TAG_PLACE_HOLDER_LINK']
    except:
        generator.settings.setdefault('FLICKR_TAG_PLACE_HOLDER_LINK','https://github.com/haum/pelican-flickrtag')        
        logger.warning ('[flickrtag]: FLICKR_TAG_PLACE_HOLDER_LINK is set to default')
    
    
    generator.settings.setdefault(
        'FLICKR_TAG_CACHE_LOCATION',
        '/tmp/com.chrisstreeter.flickrtag-images.cache')
    generator.settings.setdefault('FLICKR_TAG_INCLUDE_DIMENSIONS', False)
    generator.settings.setdefault('FLICKR_TAG_IMAGE_SIZE', 'Medium 640')


def url_for_alias(photo, alias):
    if alias == 'Medium 640':
        url = photo.getMedium640()
    else:
        url = photo.getMedium()
    url = url.replace('http:', '').replace('https:', '')
    return url


def size_for_alias(sizes, alias):
    if alias not in ('Medium 640', 'Medium'):
        alias = 'Medium'
    return [s for s in sizes if s['label'] == alias][0]

def generic_replace(generator, ct_type):
    if ct_type not in ('article', 'page'):
        ct_type = 'article'


    from jinja2 import Template

    api = generator.flickr_api_client
    if api is None:
        logger.error('[flickrtag]: Unable to get the Flickr API object')
        return

    tmp_file = generator.context.get('FLICKR_TAG_CACHE_LOCATION')

    include_dimensions = generator.context.get('FLICKR_TAG_INCLUDE_DIMENSIONS')
    size_alias = generator.context.get('FLICKR_TAG_IMAGE_SIZE')

    photo_ids = set([])
    logger.info('[flickrtag]: Parsing %ss for photo ids...' % ct_type)
    if ct_type == 'article':
        item_list = generator.articles
    else:
        item_list = generator.pages
    for item in item_list:
        for match in flickr_regex.findall(item._content):
            photo_ids.add(match[1])

    logger.info('[flickrtag]: Found %d photo ids in the %ss' % (len(photo_ids),ct_type) ) 

    try:
        with open(tmp_file, 'r') as f:
            photo_mapping = pickle.load(f)
    except (IOError, EOFError):
        photo_mapping = {}
    else:
        # Get the difference of photo_ids and what have cached
        cached_ids = set(photo_mapping.keys())
        photo_ids = list(set(photo_ids) - cached_ids)

    if photo_ids:
        logger.info('[flickrtag]: Fetching photo information from Flickr...')
        for id in photo_ids:
            logger.info('[flickrtag]: Fetching photo information for %s' % id)
            photo = api.Photo(id=id)
            # Trigger the API call...
            try:
                photo_mapping[id] = {
                    'title': photo.title,
                    'raw_url': url_for_alias(photo, size_alias),
                    'url': photo.url,
                }

                if include_dimensions:
                    sizes = photo.getSizes()
                    size = size_for_alias(sizes, size_alias)
                    photo_mapping[id]['width'] = size['width']
                    photo_mapping[id]['height'] = size['height']

            except:
                photo_mapping[id] = {
                    'title': "Placeholder",
                    'raw_url': generator.context.get('FLICKR_TAG_PLACE_HOLDER_PICT'),
                    'url': generator.context.get('FLICKR_TAG_PLACE_HOLDER_LINK'),
                }

        with open(tmp_file, 'w') as f:
            pickle.dump(photo_mapping, f)
    else:
        logger.info('[flickrtag]: Found pickled photo mapping')

    # See if a custom template was provided
    template_name = generator.context.get('FLICKR_TAG_TEMPLATE_NAME')
    if template_name is not None:
        # There's a custom template
        try:
            template = generator.get_template(template_name)
        except Exception:
            logger.error('[flickrtag]: Unable to find the custom template %s' % template_name)
            template = Template(default_template)
    else:
        template = Template(default_template)

    logger.info('[flickrtag]: Inserting photo information into %ss...' % ct_type)
    if ct_type == 'article':
        item_list = generator.articles
    else:
        item_list = generator.pages
    for item in item_list:
        for match in flickr_regex.findall(item._content):
            fid = match[1]
            if fid not in photo_mapping:
                logger.error('[flickrtag]: Could not find info for a photo!')
                continue

            # Create a context to render with
            context = generator.context.copy()
            context.update(photo_mapping[fid])

            # Render the template
            replacement = template.render(context)

            item._content = item._content.replace(match[0], replacement)


def replace_article_tags(generator):
    generic_replace(generator, 'article')


def replace_page_tags(generator):
    generic_replace(generator, 'page')


def register():
    """Plugin registration."""
    signals.generator_init.connect(setup_flickr)

    signals.article_generator_finalized.connect(replace_article_tags)
    signals.page_generator_finalized.connect(replace_page_tags)
