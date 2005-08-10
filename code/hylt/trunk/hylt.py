#!/usr/bin/env python

# hylt.py - HYperLinked Text curses-based viewer
#
# Copyright 2005 Phil Bordelon, Jochen Eisinger, Martin Ockajak, John Vernon.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
#
# (The license can be found in LICENSE.)

"""hylt v0.1.1-dev

Hylt is a text-based mini-Wiki, or something approaching that.  While
technically there is a separation between the file format and the
viewer (one could ostensibly write a GUI hylt viewer), the format
itself is meant for minimal markup.  This program implements a
curses-based viewer for Hylt files.

hylt is copyleft 2005:
   phil bordelon,
   jochen eisinger,
   martin ockajak,
   john vernon.
"""

import ConfigParser
import curses
import curses.wrapper
import optparse
import os.path
import re
import sys
import time

# SITE_CONFIG_FILE: The location of the overall site configuration file.  A
# Hylt installer should put a default config here, stating any special help
# file location, etc.

SITE_CONFIG_FILE = "/etc/hylt.conf"

# CONFIG_CONTROL_DICT: This dictionary holds the default types and values
# for configuration options.  REMEMBER TO UPDATE THIS EVERY TIME A CONFIG
# OPTION IS ADDED!

CONFIG_CONTROL_DICT = {
   "collection": {
      "editable": {
         "type": "boolean",
         "default": True
      }
   },
   "pyui": {
      "documentation_root": {
         "type": "string",
	 "default": "/usr/share/hylt/doc/pyui/Start.hylt"
      },
      "keyboard_reference": {
         "type": "string",
	 "default": "/usr/share/hylt/doc/pyui/KeyboardReference.hylt"
      },
      "editor": {
         "type": "environment",
         "variable": "EDITOR",
         "default": "vi"
      }
   }
}

def generateTitle (filename):
   """Generates the title for a given Hylt page.  This typically entails
   stripping out any directories and converting underscores to spaces.
   """
   
   to_return = ""

   # Get rid of anything before the last slash.
   basename = os.path.basename (filename)

   # Kill anything after the first period.
   primary_name = basename.split(".")[0]

   # Convert underscores to spaces.
   for char in primary_name:
      if "_" == char:
         to_return += " "
      else:
         to_return += char

   return to_return

def exportToHTML (filename, data_array, link_list):
   """Exports a given filename to an XHTML document.  The document
      is stored in the same location as the original file.
   """
   
   file = open (filename, "w")

   file.write ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
   file.write ("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.1//EN\" \"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd\">\n")
   file.write ("<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"en\">\n")
   file.write ("  <head>\n")
   file.write ("  <meta http-equiv=\"Content-Type\" content=\"application/xhtml+xml; charset=utf-8\" />\n")
   file.writelines (("    <title>", generateTitle(filename), "</title>\n"))
   file.write ("  </head>\n")
   file.write ("  <body>\n")
   file.write ("    <div id=\"main\">\n")

   for row_num in range (0, len (data_array)):

      curr_row = data_array[row_num]
      open_link = None;

      for col_num in range (0, len(curr_row)):

         (curr_char, curr_link) = curr_row[col_num]

	 if curr_link != open_link:
	    if open_link != None:
	      file.write ("</a>")

	    open_link = curr_link

	    if open_link != None:
	       link_target = link_list[open_link]
	       file.writelines (("<a href=\"", link_target[:-4], "html\">"))

	 if '<' == curr_char:
	    file.write ("&lt;")
	 elif '&' == curr_char:
	    file.write ("&amp;")
         elif '>' == curr_char:
            file.write ("&gt;")
	 else:
	    file.write (curr_char)

      if open_link != None:
	 file.write ("</a>")
      file.write ("<br/>\n")

   file.write ("    </div>\n")
   file.write ("  </body>\n")
   file.write ("</html>\n")
   file.close ()


def readHyltFile (filename, core_state):
   """Given a particular filename, this function parses it and returns the
   collection of values (in core_state) necessary for properly handling
   the display and navigation of the page.

   The parser is a finite state machine.  The FSM is actually line-based,
   and resets at the end of each line; this means that links cannot span
   newlines.
   """
   
   data_array = []

   curr_base_path = core_state["curr_base_path"]
   file = open (filename, "r")
   curr_state = "text"
   curr_link = None
   link_count = 0
   link_list = []
   max_width = 0
   has_data = False
   for line in file:
      
      new_array_line = []
      for char in line.rstrip ():
         if curr_state == "text":
            if '[' == char:
               curr_state = "firstopenbracket"
            elif '\\' == char:
               curr_state = "textescape"
            else:
               new_array_line.append ((char, None))
               has_data = True
         elif curr_state == "textescape":
            new_array_line.append ((char, None))
            curr_state = "text"
         elif curr_state == "firstopenbracket":
            if '[' == char:
               curr_state = "link_filename"
               link_filename = ""
               pretty_link = False
            else:
            
               # Gotta append the bracket that wasn't followed by another one.
               new_array_line.append (('[', None))
               new_array_line.append ((char, None))
               curr_state = "text"
         elif curr_state == "link_filename":
         
            # Convert slashes to the right direction.
            if ('\\' == char):
               link_filename += '/'
            elif ('|' == char):
            
               # Filename done; now we get the pretty print name.
               curr_state = "pretty_link"
               link_text = ""
               pretty_link = True
            elif (']' == char):
               curr_state = "firstclosebracket_normal"
            else:
               link_filename += char
         elif curr_state == "firstclosebracket_normal":
            if (']' == char):
               curr_state = "text"
              
               # Okay.  Make sure this link doesn't try to escape from the
               # base path.
               raw_link = os.path.normpath (link_filename + ".hylt")
               possible_link = os.path.join (curr_base_path, raw_link)
               safe_link = safePath (possible_link)
               if None != safe_link:

                  # Add the link to the list of links.
                  link_list.append (raw_link)

                  # We've got the full link name.  Put it into the array, with
                  # links.  Gotta kill the path first, though.
                  link_text = link_filename.split ("/")[-1]

                  for link_char in link_text:

                     # Only convert underscores.
                     if ('_' == link_char):
                        new_array_line.append ((' ', link_count))
                     else:
                        new_array_line.append ((link_char, link_count))
                  link_count += 1
                  has_data = True

               # else do nothing; this wasn't a valid link.
            else:
               curr_state = "link_filename"
               link_filename += ']'
               link_filename += char
         elif curr_state == "pretty_link":
            if (']' == char):
               curr_state = "firstclosebracket_pretty"
            else:
               link_text += char
         elif curr_state == "firstclosebracket_pretty":
            if (']' == char):
               curr_state = "text"

               # Okay.  Make sure this link doesn't try to escape from the
               # base path.
               raw_link = os.path.normpath (link_filename + ".hylt")
               possible_link = os.path.join (curr_base_path, raw_link)
               safe_link = safePath (possible_link)
               if None != safe_link:

                  # Add the link to the list of links.
                  link_list.append (raw_link)
                  
                  # Add the pretty version of the link name to the array.
                  for link_char in link_text:
                     new_array_line.append ((link_char, link_count))
                  link_count += 1
                  has_data = True
            else:
               curr_state = "pretty_link"
               link_text += ']'
               link_text += char

      # Reset state to "text" at the end of each line--no spanning links across
      # lines, too complex to handle.  If you didn't close it properly, tough.
      curr_state = "text"
      data_array.append (new_array_line)
      if len (new_array_line) > max_width:
         max_width = len (new_array_line)
  
   # Now, if we were sent to an empty file, data_array will be completely
   # empty.  We don't want that; instead, populate it with a single blank
   # space and no link.

   if not has_data:
      data_array = [[(' ', None)]]

   # Done.  Add the data array and link list to the state.
   core_state["data_array"] = data_array
   core_state["link_list"] = link_list
   core_state["link_count"] = link_count
   core_state["mx"] = max_width
   core_state["my"] = len (data_array)
   file.close ()

def displayPage (screen, core_state):
   """Displays the current Hylt page, given the current selected link, the
   size of the screen, the "cursor" location (really the top left corner
   of the screen), and so on.
   """

   if core_state["history_position"] < 0:
      return

   current_loc = core_state["history"][core_state["history_position"]]
   
   # Print everything we can fit starting where the cursor is.
   screen.clear ()
   display_y = 0
   cy = current_loc["cy"]
   cx = current_loc["cx"]
   data_array = core_state["data_array"]
   selected_link = current_loc["selected_link"]
   for row_num in range (cy, min (len (data_array), cy + core_state["y"] - 2)):
      display_x = 0
      curr_row = data_array[row_num]
      for col_num in range (cx, min (len (curr_row), cx + core_state["x"] - 1)):
         (curr_char, curr_link) = curr_row[col_num]

         if None == curr_link:

            # Blit the character plain-style.
            attribute = curses.A_NORMAL
         elif curr_link == selected_link:

            # Selected link. Inverse.
            attribute = curses.A_REVERSE
         else:

            # Bold it; it's a link, but not a selected one.
            attribute = curses.A_BOLD

         # Display and increment the column.
         screen.addch (display_y, display_x, curr_char, attribute)
         display_x += 1

      # Down to the next row!
      display_y += 1

   # Mark the screen as needing refresh.
   screen.noutrefresh ()

def debugPrintPage (data_array):
   """Prints a debug version of a page to stderr.
   """

   sys.stderr.write ("\nPage:\n")
   for row in data_array:
      char_string = ""
      link_string = ""
      for char, link in row:
         char_string += char
         if None == link:
            link_string += " "
         else:
            link_string += chr (ord ('a') + link)
      sys.stderr.write (char_string + "\n" + link_string + "\n")
   
def displayHeader (screen, core_state):
   """Displays the header for the Hylt page.
   """

   displayNote (screen, core_state["title"], core_state["x"])

def displayLinkInfo (screen, core_state):
   """Displays information based on the currently selected link on
   the Hylt page.  If there are no links on the page, displays an
   appropriate message.
   """
   
   if core_state["history_position"] < 0:
      return

   link_num = core_state["history"][core_state["history_position"]]["selected_link"]
   link_list = core_state["link_list"]
   if None != link_num:
      displayNote (screen, link_list[link_num], core_state["x"])
   else:
      displayNote (screen, "No links exist on this page.", core_state["x"])

def displayNote (screen, note, screen_width, attribute = curses.A_REVERSE):
   """Displays a 'note'--a single line of text, typically to the top
   or bottom status bars.  By default, it displays the text in
   A_REVERSE mode, as that's what the status bars usually look like;
   however, attributes can be passed which override the default.
   """
   
   screen.clear ()
   screen.attrset (attribute)
   screen.hline (0, 0, ' ', screen_width)
   screen.addnstr (0, 0, note, screen_width - 1)
   screen.noutrefresh ()

def displayBlinkingNote (screen, disp_string, x, count = 1, delay = 0.5):
   """Displays a blinking note.
   """

   for i in range (count):
      displayNote (screen, disp_string, x, curses.A_BOLD)
      curses.doupdate ()
      time.sleep (delay)
      displayNote (screen, disp_string, x, curses.A_NORMAL)
      curses.doupdate ()
      time.sleep (delay)

def noteMissingPage (screen, filename, x, count):
   """Displays a blinking message for when you attempt to navigate
   to a nonexistent Hylt page.
   """
   
   missing_str = "|" + filename + "| is missing.  Perhaps you should add it?"
   displayBlinkingNote (screen, missing_str, x, count)

def moveCursorForLink (core_state, direction):
   """When the selected link changes (usually due to an arrow
   press), the screen cursor may need to move out of the visible
   area.  This function does that while attempt to maintain
   spatial coherence--if the display was below the link, the link
   appears near the top of the page, etc.
   """

   if core_state["history_position"] < 0:
      return

   data_array = core_state["data_array"]

   if direction > 0:
      loc = 0
   else:
      loc = core_state["my"] - 1

   curr_line = data_array[loc]
   link_y = 0
   done = False
   while not done:
      for char, link in curr_line:
         if link == core_state["history"][core_state["history_position"]]["selected_link"]:
            done = True
            link_y = loc
      if not done:
         if direction > 0:
            loc += 1
         else:
            loc -= 1
         if (loc < 0) or (loc > core_state["my"] - 1):
            done = True
         else:
            curr_line = data_array[loc]

   # Okay, we have the link's y location.  If it's on the current page, don't
   # move; otherwise, do the minimal movement that gets us there.
   curr_top = core_state["history"][core_state["history_position"]]["cy"]
   curr_bottom = curr_top + core_state["y"] - 3
   if link_y < curr_top:
      distance = curr_top - link_y
      core_state["history"][core_state["history_position"]]["cy"] -= distance + 1
   elif link_y > curr_bottom:
      distance = link_y - curr_bottom
      core_state["history"][core_state["history_position"]]["cy"] += distance + 1
      
   # else do nothing; it's on this page.

def fixCursorCoords (core_state):
   """Various functions may put the screen cursor out of the
   possible range.  Instead of duplicating the errorchecking
   everywhere, a single fixCursorCoords before an attempted
   screen display can fix them up.
   """
   
   if core_state["history_position"] >= 0:
      curr_location = core_state["history"][core_state["history_position"]]
      if 0 > curr_location["cx"]:
         curr_location["cx"] = 0
      elif curr_location["cx"] > core_state["mx"] - 1:
         curr_location["cx"] = core_state["mx"] - 1
      if 0 > curr_location["cy"]:
         curr_location["cy"] = 0
      elif curr_location["cy"] > core_state["my"] - 1:
         curr_location["cy"] = core_state["my"] - 1

def safePath (path):
   """Check the attempted path to make sure that it doesn't
   attempt to escape the 'sandbox' created by the start page
   definition.  Note that things like ../ are perfectly valid
   in links; they just can't take the program out of the root
   path.  If it tries to, return None; otherwise, return the
   normalized version of the path.
   """

   to_return = None
   
   attempted_path = os.path.normpath (path)

   # Once it's normalized in the above line, the path should not
   # start with either '..' or '/', both attempts to escape.
   if not (attempted_path.startswith ("..") or
    attempted_path.startswith ("/")):
      to_return = path

   return to_return

def regexpSearchDirtree (path, expression):
   """Get a list of every file in PATH that both matches a given regular
   expression and is a Hylt file.
   """

   regexp = re.compile (expression, re.IGNORECASE)
   matches = []
   for root, dirs, files in os.walk (path):
      for file in files:
         current = os.path.join (root, file)

         # There are two criteria for adding a found file to our list:
         # - It must match the search (obviously); and
         # - It must end in .hylt.  We don't want spurious results.
         if (regexp.search (current) and len (current) > 5 and
          ".hylt" == current[-5:]):
            matches.append (current)
   return matches

def smartGo (screen, core_state):
   """Displays a 'go to' prompt on the screen; the input from that is
   fed to regexpSearchDirtree, and that output is passed out to the
   caller.
   """

   prompt = "Go to: "
   displayNote (screen, prompt, core_state["x"] - 1)
   curses.curs_set (1)
   curses.echo ()
   expression = screen.getstr (0, len (prompt))
   curses.noecho ()
   curses.curs_set (0)
   displayNote (screen, "Searching for: " + expression, core_state["x"] - 1)
   return regexpSearchDirtree (".", expression)

def generateConfiguration ():
   """Generate a configuration for a given instance of Hylt.  There
   are multiple config file locations that we need to read from,
   and various default values that must be set if not present in
   the config files.
   """

   config_file_list = [
      SITE_CONFIG_FILE,
      os.path.expanduser ("~/.hylt.conf"),
      "hylt.conf"
   ]

   config_parser = ConfigParser.ConfigParser ()
   config_parser.read (config_file_list)

   # Since every possible configuration option is in CONFIG_CONTROL_DICT,
   # we use that as the source for the real config; that way bogus
   # configuration options don't throw us off.  (We try to be helpful,
   # honest.)
   real_config = {}

   for sect, sect_dict in CONFIG_CONTROL_DICT.items():
      real_config[sect] = {}
      for opt, opt_dict in sect_dict.items():

         # Okay.  At the moment, there are two elements in every entry:
         # - "type": "string", "int", "bool", "environment"
         # - "variable": Environment variable that holds value if not in file
         # - "default": a default value for the element.

         # First, make sure it even has a value for this; if not, just
         # use the default.
         if not config_parser.has_option (sect, opt):
           
            # There's no value; just use the default ... unless it's an
            # environment variable, in which case we try the environment
            # variable first as a fallback.
            if "environment" == opt_dict["type"]:
               real_config[sect][opt] = os.getenv (opt_dict["variable"],
                opt_dict["default"])
            else:
               real_config[sect][opt] = opt_dict["default"]

         else:
            
            # Okay, there's a value.  Determine what function we're
            # going to use to fetch the value.
            if "integer" == opt_dict["type"]:
               fetch_function = config_parser.getint
            elif "boolean" == opt_dict["type"]:
               fetch_function = config_parser.getboolean
            else: # "string" or "environment" == opt_dict["type"]
               fetch_function = config_parser.get

            # Now that we have a function handle, use it in a try/except
            # block.  If there's any exception, set the value to the
            # default, as it's bum data.

            try:
               opt_value = fetch_function (sect, opt)
            except:
               sys.stderr.write ("ERROR: Configuration file option " + opt +
                " in section " + sect + " is incorrectly set.  Using the" +
                " default.  Please check your configuration.\n")
               opt_value = opt_dict["default"]
                  
            real_config[sect][opt] = opt_value

   # Done generating the configuration!  Return it.
   return real_config

def historyCut (core_state):
   """ Remove all forward history (from current position)
   """

   # We have to remove everything past the history_position, as
   # selecting a link kills history.
   #
   #   len (history) = history_postion - 1
   #
   # which makes the slice just [:].  Very clever.
   core_state["history"] = core_state["history"][:core_state["history_position"] + 1]
   return len (core_state["history"])

def historyAdd (core_state, filename):
   """Add a page to the history. It's new file so there is no knowledge
   of locations on the page, etc.
   """

   # Populate the history object and append it to the history stream.
   history_dict = {
      "filename": filename,
      "cx": 0,
      "cy": 0,
      "selected_link": 0
   }
   core_state["history"].append (history_dict)
   return len (core_state["history"])

def historyMove (core_state, step):
   """ Load a page from the forward (positive step) or backward (negative
   step) history; return the real number of steps if the move was successful
   and 0 otherwise.
   """

   old_pos = core_state["history_position"]
   core_state["history_position"] = max (0, min (old_pos + step, 
    len (core_state["history"]) - 1))
   if (core_state["history_position"] != old_pos and
    core_state["history_position"] >= 0):
      return core_state["history_position"] - old_pos
   else:
      return 0


def invokeEditor (editor, filename):
   """Invoke an editor via spawnlp.
   """

   # We need to make any missing subdirectories in the path.
   path_to_check = os.path.dirname (filename)
   should_edit = True
   if not os.path.exists (path_to_check):
      try:
         os.makedirs (os.path.dirname (filename))
      except:
         # Something bad happened; probably a dead symlink.  No real error
         # handling code yet, so just don't bother invoking the editor.
         # (Of course, it could be a perms issue, which means this might
         # actually be common.  Ah, well.  We'll deal with this at some
         # later date.)
         should_edit = False

   if should_edit:
      os.spawnlp (os.P_WAIT, editor, editor, filename)

def convertFilenameToHylt (filename):
   """Converts a filename to a potential Hylt filename.
   """

   # Add /Start.hylt at the end if the last five characters aren't .hylt.
   potential_filename = args[0]
   if (len (potential_filename) < 5) or (".hylt" != potential_filename[-5:]):
      potential_filename += "/Start.hylt"

   return (os.path.normpath (potential_filename))

def hyltMain (meta_screen, starting_filename):
   """The core Hylt functionality.  Contains the main input and
   display loops, lots of initialization, and so on.
   """

   curses.curs_set(0)

   # Remember: Parameters are in the order of (y, x).
   meta_y, meta_x = meta_screen.getmaxyx()
   core_state = {"y": meta_y, "x": meta_x}

   # Change to the base path.
   os.chdir (os.path.dirname (starting_filename))
   core_state["curr_base_path"] = ""
   

   # There are three windows: a top status bar, a primary screen, and a bottom
   # status bar.  There is also the main screen, of course.  Create them.
   top = meta_screen.subwin (1, meta_x, 0, 0)
   main = meta_screen.subwin (meta_y - 2, meta_x, 1, 0)
   bottom = meta_screen.subwin (1, meta_x, meta_y - 1, 0)

   # Read in the configuration.
   config = core_state["config"] = generateConfiguration ()

   editor = config["pyui"]["editor"]

   # Okay.  History's actually a bad name for this right now, but it'll have
   # to do.  This is a list of pages; it normally tracks history, but can
   # also track search results.  At the beginning, the only element in the
   # history is the starting page; others will be added, subtracted, etc.
   core_state["history"] = []
   historyAdd(core_state, os.path.basename (starting_filename))
   core_state["history_position"] = 0

   fresh_page = True
   done = False

   curses.def_prog_mode ()

   main_needs_redraw = True

   while not done:
      current_loc = core_state["history"][core_state["history_position"]]
      if fresh_page:

         filename = current_loc["filename"]
         core_state["curr_base_path"] = os.path.dirname (filename)

         readHyltFile (filename, core_state) 
#        debugPrintPage (core_state["data_array"])

         core_state["title"] = generateTitle (filename)

         # Links can be removed between page loads, and the history
         # jumper defaults to link 0, which doesn't exist on a page
         # with no links.  In either case, we're safe if we just
         # change the link count to something more appropriate.
         current_loc["selected_link"] = min(current_loc["selected_link"], core_state["link_count"] - 1)
         if current_loc["selected_link"] == -1:
            current_loc["selected_link"] = None
     
         dir_delta = 1
         fresh_page = False
         main_needs_redraw = True
         displayHeader (top, core_state)
         displayLinkInfo (bottom, core_state)

      fixCursorCoords (core_state)
      if main_needs_redraw:
         displayPage (main, core_state)
      curses.doupdate ()
      keypress = meta_screen.getch()
      if ord ('q') == keypress:
         done = True
      elif ord ('h') == keypress:
         current_loc["cx"] -= min (max (1, meta_x / 2), 8)
         main_needs_redraw = True
      elif ord ('j') == keypress:
         current_loc["cy"] += min (max (1, meta_x / 2), 8)
         main_needs_redraw = True
      elif ord ('k') == keypress:
         current_loc["cy"] -= min (max (1, meta_x / 2), 8)
         main_needs_redraw = True
      elif ord ('l') == keypress:
         current_loc["cx"] += min (max (1, meta_x / 2), 8)
         main_needs_redraw = True
      elif ord ('x') == keypress:
         exportToHTML (filename[:-4] + "html",
          core_state["data_array"], core_state["link_list"])
         displayNote (bottom, "Exported to '" + filename[:-4]
          + "html' ...", core_state["x"])
      elif curses.KEY_NPAGE == keypress:
         current_loc["cy"] += meta_y - 4
         main_needs_redraw = True
      elif curses.KEY_PPAGE == keypress:
         current_loc["cy"] -= meta_y - 4
         main_needs_redraw = True
      elif ord ('[') == keypress:
         current_loc["cx"] -= meta_x - 4
         main_needs_redraw = True
      elif ord (']') == keypress:
         current_loc["cx"] += meta_x - 4
         main_needs_redraw = True
      elif ord ('r') == keypress:
         fresh_page = True

      # Extended regular expression based pathname matching, working directory
      # tree breadth-first traversing and search result based forward page
      # history list creating 'go' feature (note: full room service is not
      # included in trial version)
      elif ord ('g') == keypress:
         result = smartGo(bottom, core_state)
         if len(result):
            historyCut (core_state)
            for page in result:
               historyAdd (core_state, page)
               sys.stderr.write(page + "\n")
            historyMove (core_state, 1)
            fresh_page = True
         else:
            displayNote(bottom, "No matching files found", core_state["x"] - 1)
         
      elif (curses.KEY_LEFT == keypress or curses.KEY_BACKSPACE == keypress or
       ord (',') == keypress):
         if historyMove (core_state, -1):
            fresh_page = True

      elif ord ('.') == keypress:
         if historyMove (core_state, 1):
            fresh_page = True

      # Don't even bother with arrow keys other than back unless link count > 0.
      elif core_state["link_count"] > 0:
         if curses.KEY_UP == keypress:
            if current_loc["selected_link"] == 0:
               current_loc["cy"] -= min (max (1, meta_x / 2), 8)
               dir_delta = -1
            else:
               current_loc["selected_link"] -= 1
               moveCursorForLink (core_state, -1)
               displayLinkInfo (bottom, core_state)
            main_needs_redraw = True

         elif curses.KEY_DOWN == keypress:
            if current_loc["selected_link"] == core_state["link_count"] - 1:
               current_loc["cy"] += min (max (1, meta_x / 2), 8)
               dir_delta = -1
            else:
               current_loc["selected_link"] += 1
               moveCursorForLink (core_state, 1)
               displayLinkInfo (bottom, core_state)
            main_needs_redraw = True

         elif ord (' ') == keypress:
            moveCursorForLink (core_state, dir_delta)
            main_needs_redraw = True

         elif ord ('E') == keypress:
            if config["collection"]["editable"]:
               dest = os.path.join (core_state["curr_base_path"],
                core_state["link_list"][current_loc["selected_link"]])

               invokeEditor (editor, dest)

               curses.reset_prog_mode ()
               curses.curs_set(1)
               curses.curs_set(0)
               main_needs_redraw = True
               displayHeader (top, core_state)
               displayLinkInfo (bottom, core_state)

         elif ord ('e') == keypress:
            if config["collection"]["editable"]:
               invokeEditor (editor, filename)

               curses.reset_prog_mode ()
               curses.curs_set(1)
               curses.curs_set(0)
               fresh_page = True
               curr_loc_info = None

         elif ord ('d') == keypress:
            if os.path.isfile (config["pyui"]["documentation_root"]):
               current_directory = os.getcwd ()
               hyltMain (meta_screen,config["pyui"]["documentation_root"])
               os.chdir (current_directory)
         
         elif ord ('?') == keypress:
            if os.path.isfile (config["pyui"]["keyboard_reference"]):
               current_directory = os.getcwd ()
               hyltMain (meta_screen,config["pyui"]["keyboard_reference"])
               os.chdir (current_directory)
         
         elif (curses.KEY_RIGHT == keypress or 10 == keypress or
          curses.KEY_ENTER == keypress):
         
            # The big one--jump to a new Hylt page.  First, make sure it's a
            # real page.
            rel_name = core_state["link_list"][current_loc["selected_link"]]
            real_path = os.path.normpath (os.path.join (
             core_state["curr_base_path"], rel_name))
            if os.path.isfile (real_path):
               historyCut (core_state)
               historyAdd (core_state, real_path)
               historyMove (core_state, 1)
               fresh_page = True
            else:
               displayNote (bottom, "|" + rel_name +
                "| not found. Do you want to create this file? [y/N] ",
                core_state["x"] - 1)
               response = bottom.getch (0, 0)
               if ord ('y') == response or ord ('Y') == response:
                  invokeEditor (editor, real_path)

                  curses.reset_prog_mode ()
                  curses.curs_set(1)
                  curses.curs_set(0)
               displayNote(bottom, real_path, core_state["x"] - 1)
               

if "__main__" == __name__:
   core_state = {}
   option_parser = optparse.OptionParser ()
   options, args = option_parser.parse_args ()
   if len (args) == 1:
      filename = convertFilenameToHylt (args[0])
   elif len (args) == 0:
      filename = "./Start.hylt"
   else:
      print "ERROR: You must pass either no parameters (which uses index.hylt)"
      print "or a single filename to use."
      sys.exit (0)
   curses.wrapper (hyltMain, filename)
