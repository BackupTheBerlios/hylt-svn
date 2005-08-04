#!/usr/bin/env python

##########
#
# hylt v0.1.0
#
# copyleft 2005 phil bordelon
#
##########

import curses
import curses.wrapper
import optparse
import os.path
import sys
import time

exit_message = "Thanks for using Hylt!"

def redrawWindows (window_dict):
   for elem_dict in window_dict.values ():
      if True == elem_dict["r"]:
         elem_dict["w"].noutrefresh ()
         elem_dict["r"] = False
   curses.doupdate ()

def generateTitle (filename):
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

###

###
# export the wiki page in core_states to the XHTML document 'filename'
#
def exportToHTML (filename, core_state):
   
   data_array = core_state["data_array"]
   link_list = core_state["link_list"]
   
   file = open (os.path.join (core_state["base_path"], filename), "w")

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

	 if curr_char == '<':
	    file.write ("&lt;")
	 elif curr_char == '&':
	    file.write ("&amp;")
	 else:
	    file.write (curr_char)

      if open_link != None:
	 file.write ("</a>\n")
      file.write ("<br/>\n")

   file.write ("    </div>\n")
   file.write ("  </body>\n")
   file.write ("</html>\n")
   file.close ()


def readHyltFile (filename, core_state):

   data_array = []

   file = open (os.path.join (core_state["base_path"], filename), "r")
   curr_state = "text"
   curr_link = None
   link_count = 0
   link_list = []
   max_width = 0
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
# We've got the full link name.  Put it into the array, with links.
# Gotta kill the path first, though.
               link_text = link_filename.split ("/")[-1]
               link_list.append (os.path.normcase(link_filename + ".hylt"))
               for link_char in link_text:
# Only convert underscores.
                  if ('_' == link_char):
                     new_array_line.append ((' ', link_count))
                  else:
                     new_array_line.append ((link_char, link_count))
               link_count += 1
            else:
               curr_state = "link_filename"
               link_filename += ']'
               link_text += char
         elif curr_state == "pretty_link":
            if (']' == char):
               curr_state = "firstclosebracket_pretty"
            else:
               link_text += char
         elif curr_state == "firstclosebracket_pretty":
            if (']' == char):
               curr_state = "text"
               link_list.append (os.path.normcase(link_filename + ".hylt"))
               for link_char in link_text:
                  new_array_line.append ((link_char, link_count))
               link_count += 1
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
   
# Done.  Add the data array and link list to the state.
   core_state["data_array"] = data_array
   core_state["link_list"] = link_list
   core_state["link_count"] = link_count
   core_state["mx"] = max_width
   core_state["my"] = len (data_array)
   file.close ()

def displayPage (screen, core_state):

   screen.clear ()
# Print everything we can fit starting where the cursor is.

   display_y = 0
   cy = core_state["cy"]
   cx = core_state["cx"]
   data_array = core_state["data_array"]
   selected_link = core_state["selected_link"]
   for row_num in range (cy, min (len (data_array), cy + core_state["y"] - 2)):
      display_x = 0
      curr_row = data_array[row_num]
      for col_num in range (cx, min (len (curr_row), cx + core_state["x"] - 1)):
         (curr_char, curr_link) = curr_row[col_num]

         if None == curr_link:
# Blit the character plain-style.
            attribute = curses.A_NORMAL
         elif curr_link == selected_link:
# Inverse.
            attribute = curses.A_REVERSE
         else:
# Bold it; it's a link, but not a selected one.
            attribute = curses.A_BOLD

# Display and increment the column.
         screen.addch (display_y, display_x, curr_char, attribute)
         display_x += 1

# Down to the next row!
      display_y += 1

def displayHeader (screen, core_state):
   screen.clear ()
   screen.attrset (curses.A_REVERSE)
   screen.hline (0, 0, ' ', core_state["x"])
   screen.addnstr (0, 0, core_state["title"], core_state["x"] - 1)

def displayLinkInfo (screen, core_state):
   screen.clear ()
   screen.attrset (curses.A_REVERSE)
   screen.hline (0, 0, ' ', core_state["x"])
   link_num = core_state["selected_link"]
   link_list = core_state["link_list"]
   if None != link_num:
      screen.addnstr (0, 0, link_list[link_num], core_state["x"] - 1)

def displayNote (screen, note, core_state):
   screen.clear ()
   screen.attrset (curses.A_REVERSE)
   screen.hline (0, 0, ' ', core_state["x"])
   screen.addnstr (0, 0, note, core_state["x"] - 1)
   screen.noutrefresh ()

def noteMissingPage (screen, filename, x):
   print_str = "|" + filename + "| is missing.  Perhaps you should add it?"
   for i in range (3):
      screen.clear ()
      screen.attrset (curses.A_BOLD)
      screen.hline (0, 0, ' ', x)
      screen.addnstr (0, 0, print_str, x - 1)
      screen.noutrefresh ()
      curses.doupdate ()
      time.sleep (0.5)
      screen.clear ()
      screen.attrset (curses.A_NORMAL)
      screen.hline (0, 0, ' ', x)
      screen.addnstr (0, 0, print_str, x - 1)
      screen.noutrefresh ()
      curses.doupdate ()
      time.sleep (0.5)

def moveCursorForLink (core_state, direction):

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
         if link == core_state["selected_link"]:
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
   curr_top = core_state["cy"]
   curr_bottom = curr_top + core_state["y"] - 3
   if link_y < curr_top:
      distance = curr_top - link_y
      core_state["cy"] -= distance + 1
   elif link_y > curr_bottom:
      distance = link_y - curr_bottom
      core_state["cy"] += distance + 1
# else do nothing; it's on this page.

def fixCursorCoords (core_state):
   if 0 > core_state["cx"]:
      core_state["cx"] = 0
   elif core_state["cx"] > core_state["mx"] - 1:
      core_state["cx"] = core_state["mx"] - 1
   if 0 > core_state["cy"]:
      core_state["cy"] = 0
   elif core_state["cy"] > core_state["my"] - 1:
      core_state["cy"] = core_state["my"] - 1

def hyltMain (meta_screen, starting_filename):

   curses.curs_set(0)

# Remember: Parameters in the order of (y, x).
   meta_y, meta_x = meta_screen.getmaxyx()
   core_state = {"y": meta_y, "x": meta_x}

# Keep the "base path", as all Hylt links are relative.
# TODO: Keep people from backing out of the base path using .. or the like.
   core_state["base_path"] = os.path.dirname (starting_filename)
   filename = os.path.basename (starting_filename)
   

# There are three windows: a top status bar, a primary screen, and a bottom
# status bar.  There is also the main screen, of course.  Create them.
   top = meta_screen.subwin (1, meta_x, 0, 0)
   main = meta_screen.subwin (meta_y - 2, meta_x, 1, 0)
   bottom = meta_screen.subwin (1, meta_x, meta_y - 1, 0)

   window_dict = {
      "top": {"w": top, "r": True},
      "main": {"w": main, "r": True},
      "bottom": {"w": bottom, "r": True}
   }

   core_state["history"] = []

   fresh_page = True
   done = False

   curses.def_prog_mode ()

   while not done:

      if fresh_page:
         readHyltFile (filename, core_state) 

         core_state["title"] = generateTitle (filename)
         core_state["cx"] = 0
         core_state["cy"] = 0
         if core_state["link_count"] > 0:
            core_state["selected_link"] = 0
         else:
            core_state["selected_link"] = None
     
         window_dict["top"]["r"] = True
         window_dict["main"]["r"] = True
         window_dict["bottom"]["r"] = True
         dir_delta = 1
         fresh_page = False

      fixCursorCoords (core_state)
      if True == window_dict["top"]["r"]:
         displayHeader (top, core_state)
      if True == window_dict["main"]["r"]:
         displayPage (main, core_state)
      if True == window_dict["bottom"]["r"]:
         displayLinkInfo (bottom, core_state)
      redrawWindows (window_dict)
      keypress = meta_screen.getch()
      if ord ('q') == keypress:
         done = True
      elif ord ('h') == keypress:
         core_state["cx"] -= min (max (1, meta_x / 2), 8)
         window_dict["main"]["r"] = True
      elif ord ('j') == keypress:
         core_state["cy"] += min (max (1, meta_x / 2), 8)
         window_dict["main"]["r"] = True
      elif ord ('k') == keypress:
         core_state["cy"] -= min (max (1, meta_x / 2), 8)
         window_dict["main"]["r"] = True
      elif ord ('l') == keypress:
         core_state["cx"] += min (max (1, meta_x / 2), 8)
         window_dict["main"]["r"] = True
      elif ord ('x') == keypress:
	 exportToHTML (filename[:-4] + "html", core_state)
	 displayNote (bottom, "Exported to '" + filename[:-4] + "html' ...", core_state)
      elif curses.KEY_NPAGE == keypress:
         core_state["cy"] += meta_y - 4
         window_dict["main"]["r"] = True
      elif curses.KEY_PPAGE == keypress:
         core_state["cy"] -= meta_y - 4
         window_dict["main"]["r"] = True
      elif ord ('r') == keypress:
         fresh_page = True

      elif curses.KEY_LEFT == keypress:
         if len (core_state["history"]) > 0:
            filename = core_state["history"][-1]
            core_state["history"].pop ()
            fresh_page = True

# Don't even bother with arrow keys other than back unless link count > 0.
      elif core_state["link_count"] > 0:
         if curses.KEY_UP == keypress:
            if core_state["selected_link"] == 0:
               core_state["cy"] -= min (max (1, meta_x / 2), 8)
               dir_delta = -1
            else:
               core_state["selected_link"] -= 1
               moveCursorForLink (core_state, -1)
               window_dict["bottom"]["r"] = True
            window_dict["main"]["r"] = True

         elif curses.KEY_DOWN == keypress:
            if core_state["selected_link"] == core_state["link_count"] - 1:
               core_state["cy"] += min (max (1, meta_x / 2), 8)
               dir_delta = -1
            else:
               core_state["selected_link"] += 1
               moveCursorForLink (core_state, 1)
               window_dict["bottom"]["r"] = True

            window_dict["main"]["r"] = True

         elif ord (' ') == keypress:
            moveCursorForLink (core_state, dir_delta)
            window_dict["main"]["r"] = True

         elif ord ('e') == keypress:
            if None != os.getenv ("EDITOR", None):
               rel_name = core_state["link_list"][core_state["selected_link"]]
               real_filename = os.path.join (core_state["base_path"], rel_name)
               os.system (os.getenv ("EDITOR") + " \"" + real_filename + "\"")

               curses.reset_prog_mode ()
               curses.curs_set(1)
               curses.curs_set(0)
               window_dict["top"]["r"] = True
               window_dict["main"]["r"] = True
               window_dict["bottom"]["r"] = True

         elif ord ('E') == keypress:
            if None != os.getenv ("EDITOR", None):
               real_filename = os.path.join (core_state["base_path"], filename)
               os.system (os.getenv ("EDITOR") + " \"" + real_filename + "\"")
              
               curses.reset_prog_mode ()
               curses.curs_set(1)
               curses.curs_set(0)
               fresh_page = True

         elif curses.KEY_RIGHT == keypress:
# The big one--jump to a new Hylt page.  First, make sure it's a real page.
            rel_name = core_state["link_list"][core_state["selected_link"]]
            real_filename = os.path.join (core_state["base_path"], rel_name)
            if os.path.isfile (real_filename):
# Go!  Add this page to the history so we can come back.
               core_state["history"].append (filename)
               filename = rel_name
               fresh_page = True
            else:
               noteMissingPage (bottom, rel_name, core_state["x"])
               window_dict["bottom"]["r"] = True
               

if "__main__" == __name__:
   core_state = {}
   option_parser = optparse.OptionParser ()
   options, args = option_parser.parse_args ()
   if len (args) == 1:
      filename = os.path.normpath(args[0])
   elif len (args) == 0:
      filename = "Start.hylt"
   else:
      print "ERROR: You must pass either no parameters (which uses index.hylt)"
      print "or a single filename to use."
      sys.exit (0)
   curses.wrapper (hyltMain, filename)
   print exit_message
