# -*- coding: utf-8 -*-
#
# This file is execfile()d with the current directory set to its containing dir.

import sys
import os

PATH = os.path.dirname(os.path.abspath(__file__))


# -- General configuration -----------------------------------------------------

project = u'MMRI'
copyright = u'2013, Beter Benutten MMRI consortia'

version = 'current'  # major.minor
release = 'current'  # full version

master_doc = 'index'
source_suffix = '.rst'
templates_path = ['.templates']
exclude_patterns = ['.build']

extensions = [
    'sphinx.ext.intersphinx', 
    'sphinx.ext.todo',
]

pygments_style = 'friendly'

intersphinx_mapping = {
}


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'goabout'
html_theme_path = ['.themes']
#html_theme_options = {}

html_title = 'MMRI documentation'
html_static_path = ['.static']
html_logo = 'bblogo.jpg'
html_favicon = 'favicon.ico'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

html_domain_indices = False
html_use_index = False
html_show_sourcelink = False
#html_show_sphinx = True
