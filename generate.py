import os
import shutil
import codecs
import cgi
import urllib2
import json

from docutils.core import publish_doctree

from mako.template import Template
from mako.lookup import TemplateLookup

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


def hilite(node):
    lexer = 'text'
    if 'classes' in node.attributes:
        classes = node.attributes['classes']
        if len(classes) == 2:
            lexer = node.attributes['classes'][-1]

    code = node.astext()
    lexer = get_lexer_by_name(lexer)
    formatter = HtmlFormatter(style='colorful')
    return highlight(code, lexer, formatter)


_SERVER = 'http://short.faitmain.org'
_KEY = 'booba82'


src = 'src'
target = 'build'
media = os.path.abspath(os.path.join(target, 'media'))
_GENERIC = os.path.join(src, 'generic.mako')
_ICONS = ('pen.png', 'info.png', 'thumbsup.png',
          'right.png', 'flash.png')


def _notag(text):
    return cgi.escape(text)


def shorten(url):
    req = urllib2.Request(_SERVER, headers={'X-Short': _KEY})
    req.get_method = lambda: 'POST'
    req.add_data(url)
    res = urllib2.urlopen(req).read()
    res = json.loads(res)
    return _SERVER + '/' + res['short']


SIMPLE_TAGS = {
    # node tagname: (html tagname, strip child?)
    'paragraph': ('p', False),
    'emphasis': ('em', False),
    'strong': ('strong', False),
    'literal': ('pre', False),
    'bullet_list': ('ul', False),
    'enumerated_list': ('ol', False),
    'list_item': ('li', True),
    'table': ('table', True),
    'thead': ('thead', False),
    'tbody': ('tbody', False),
    'row': ('tr', False),
}


def render_simple_tag(node, tagname=None, strip_child=False):
    """Render a tag using the simplest default method.

    If tagname is provided, it is used instead of the node.tagname attribute.
    If strip_child is True, then the (single) child is stripped and its
    children are rendered instead.

    """
    if tagname is None:
        tagname = node.tagname
    attributes = ['%s="%s"' % (attr, value) for attr, value in node.attlist()]
    rendered = ['<%s>' % tagname]
    if attributes:
        rendered[0] = '<%s %s>' % (tagname, " ".join(attributes))
    if node.children and strip_child:
        node = node.children[0]
    for child in node.children:
        rendered.append(_tree(child))
    rendered.append('</%s>' % tagname)
    return rendered


def _tree(node):
    """Renders a node in HTML.
    """
    text = []
    klass = node.__class__.__name__
    if klass == 'transition':
        text.append('<hr/>')
    elif klass == 'system_message':
        pass
    elif klass == 'Text':
        text.append(node.astext())
    elif klass == 'literal_block':
        text.append('<div class="syntax rounded">')
        text.append(hilite(node))
        text.append('</div>')
    elif klass == 'note':
        node.attributes['class'] = 'well note'
        text.extend(render_simple_tag(node, 'div', strip_child=True))
    elif klass == 'image':
        nolegend = False
        if node.hasattr('uri'):
            uri = node['uri']
            file_ = os.path.split(uri)[-1]
            if file_ in _ICONS:
                class_ = 'subst'
                nolegend = True
            else:
                text.append('<div>')
                class_ = 'centered'
            text.append('<img class="%s" src="%s">' % (class_, uri))
        else:
            text.append('<div>')
            text.append('<img class="centered">')

        for child in node.children:
            text.append(_tree(child))

        text.append('</img>')
        if not nolegend and 'alt' in node:
            text.append('<span class="legend">')
            text.append(node['alt'])
            text.append('</span>')
            text.append('</div>')
    elif klass == 'reference':  # link
        if node.hasattr('refid'):
            text.append('<a href="#%s">' % node['refid'])
        elif node.hasattr('refuri'):
            refuri = node['refuri']
            if 'wikipedia.org' in refuri:
                text.append('<a href="%s" class="wikipedia">' % refuri)
            else:
                if 'faitmain.org' not in refuri and not refuri.startswith('/'):
                    refuri = shorten(refuri)
                text.append('<a href="%s">' % refuri)
        else:
            text.append('<a>')
        for child in node.children:
            text.append(_tree(child))
        text.append('</a>')
    elif klass == 'target':
        # ??
        pass
    elif klass == 'section':
        text.append('<h2>%s</h2>' % node.children[0][0].astext())
        for child in node.children[1:]:
            text.append(_tree(child))
    elif klass == 'substitution_definition':
        #uri = node.children[0].attributes['uri']
        #text.append('<img class="subst" src="%s"></img>' % uri)
        pass
    elif klass == 'colspec':  # table colspec
        pass
    elif klass == 'entry':  # table entry
        tagname = 'td'
        if node.parent.parent.tagname == 'thead':
            tagname = 'th'
        text.extend(render_simple_tag(node, tagname, strip_child=True))
    elif klass in SIMPLE_TAGS:
        tagname, strip_child = SIMPLE_TAGS[klass]
        text.extend(render_simple_tag(node, tagname, strip_child=strip_child))
    else:
        raise NotImplementedError(node)

    return ' '.join(text)


_FOOTER = """
.. |pen| image:: http://cnd.faitmain.org/media/pen.png
.. |info| image:: http://cnd.faitmain.org/media/info.png
.. |thumbsup| image:: http://cnd.faitmain.org/media/thumbsup.png
.. |right| image:: http://cnd.faitmain.org/media/right.png
.. |flash| image:: http://cnd.faitmain.org/media/flash.png

"""


def generate():
    if not os.path.exists(target):
        os.mkdir(target)

    lookup = TemplateLookup(directories=['.'])

    for root, dirs, files in os.walk(src):
        for file in files:
            ext = os.path.splitext(file)[-1]
            path = os.path.join(root, file)

            if ext in ('.mako', '.un~'):
                continue

            # getting read of '/src
            location = path[len('src/'):]
            file_target = os.path.join(target, location)
            print 'Generating %r' % file_target
            target_dir = os.path.dirname(file_target)

            if not os.path.exists(target_dir):
                os.makedirs(target_dir)

            if ext == '.html':
                mytemplate = Template(filename=path, lookup=lookup)

                with codecs.open(file_target, 'w', encoding='utf8') as f:
                    f.write(mytemplate.render())
            elif ext == '.rst':
                # generating the tree, then creating a mako document
                with open(path) as f:
                    content = f.read() + _FOOTER
                    doctree = publish_doctree(content)

                title = doctree.children[0].astext()

                paragraphs = ['<p>%s</p>' % _tree(text)
                              for text in doctree.children[1:]]

                mytemplate = Template(filename=_GENERIC, lookup=lookup)

                file_target = os.path.splitext(file_target)[0] + '.html'
                with codecs.open(file_target, 'w', encoding='utf8') as f:
                    f.write(mytemplate.render(body='\n'.join(paragraphs),
                                              title=title))

            else:
                shutil.copyfile(path, file_target)

    # media
    if os.path.exists(media):
        shutil.rmtree(media)
    shutil.copytree('media', media)


if __name__ == '__main__':
    generate()
