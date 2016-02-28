###############################################################################
##
## config.rb
## rainwatch: Compass Project Configuration
##
## @author		Jacob Hipps - jacob@ycnrg.org
## @param 		vim: set ts=4 sw=4 noexpandtab syntax=ruby:
##
## @repo		https://bitbucket.org/yellowcrescent/rainwatch
##
###############################################################################
require 'compass/import-once/activate'

# Require any additional compass plugins here.

# Set this to the root of your project when deployed:
http_path = ""
css_dir = "css"
sass_dir = "sass"
images_dir = "img"
javascripts_dir = "js"

# You can select your preferred output style here (can be overridden via the command line):
# output_style = :expanded or :nested or :compact or :compressed
output_style = :expanded

# To enable relative paths to assets via compass helper functions. Uncomment:
# relative_assets = true

# Misc options
line_comments = false
preferred_syntax = :scss
sourcemap = false
disable_warnings = true
sass_options = { :cache => false }

