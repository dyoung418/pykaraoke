#!/usr/bin/env python

# pycdg - CDG/MP3+G Karaoke Player

# Copyright (C) 2005  Kelvin Lawson (kelvinl@users.sourceforge.net)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


# OVERVIEW
#
# pycdg is a CDG karaoke player which supports MP3+G and OGG+G tracks.
#
# The player uses the pygame library (www.pygame.org), and can therefore
# run on any operating system that runs pygame (currently Linux, Windows
# and OSX).
#
# You can use this file as a standalone player, or together with
# PyKaraoke. PyKaraoke provides a graphical user interface, playlists,
# searchable song database etc.
#
# For those writing a media player or similar project who would like
# CDG support, this module has been designed to be easily incorporated
# into such projects and is released under the LGPL.


# REQUIREMENTS
#
# pycdg requires the following to be installed on your system:
# . Python (www.python.org)
# . Pygame (www.pygame.org)

# . Numeric module (numpy.sourceforge.net) (actually, this is required
#    only if you do not use the compiled C low-level CDG implementation in
#    _pycdgAux.c)


# USAGE INSTRUCTIONS
#
# To start the player, pass the CDG filename/path on the command line:
#       python pycdg.py /songs/theboxer.cdg
#
# You can also incorporate a CDG player in your own projects by
# importing this module. The class cdgPlayer is exported by the
# module. You can import and start it as follows:
#   import pycdg
#   player = pycdg.cdgPlayer("/songs/theboxer.cdg")
#   player.Play()
# If you do this, you must also arrange to call pycdg.manager.Poll()
# from time to time, at least every 100 milliseconds or so, to allow
# the player to do its work.
#
# The class also exports Close(), Pause(), Rewind(), GetPos().
#
# There are two optional parameters to the initialiser, errorNotifyCallback
# and doneCallback:
#
# errorNotifyCallback, if provided, will be used to print out any error
# messages (e.g. song file not found). This allows the module to fit 
# together well with GUI playlist managers by utilising the same GUI's
# error popup window mechanism (or similar). If no callback is provided,
# errors are printed to stdout. errorNotifyCallback should take one 
# parameter, the error string, e.g.:
#   def errorPopup (ErrorString):
#       msgBox (ErrorString)
#
# doneCallback can be used to register a callback so that the player
# calls you back when the song is finished playing. The callback should
# take no parameters, e.g.:
#   def songFinishedCallback():
#       msgBox ("Song is finished")
#
# To register callbacks, pass the functions in to the initialiser:
#   cdgPlayer ("/songs/theboxer.cdg", errorPopup, songFinishedCallback)
# These parameters are optional and default to None.
#
# If the initialiser fails (e.g. the song file is not present), __init__
# raises an exception.


# IMPLEMENTATION DETAILS
#

# pycdg is implemented as a handful of python modules.  All of the CDG
# decoding is handled in the C module _pycdgAux.c, or in the
# equivalent (but slightly slower) pycdgAux.py if the C module is not
# available for some reason.  This Python implementation of
# pycdgAux.py uses the python Numeric module, which provides fast
# handling of the arrays of pixel data for the display.
#
# Audio playback and video display capabilities come from the pygame
# library.
#
# All of the information on the CDG file format was learned
# from the fabulous "CDG Revealed" tutorial at www.jbum.com.
#

# Previous implementations ran the player within a thread; this is no
# longer the case.  Instead, it is the caller's responsibility to call
# pycdg.manager.Poll() every once in a while to ensure that the player
# gets enough CPU time to do its work.  Ideally, this should be at
# least every 100 milliseconds or so to guarantee good video and audio
# response time.
#
# At each call to Poll(), the player checks the current time in the
# song. It reads the CDG file at the correct location for the current
# position of the song, and decodes the CDG commands stored there. If
# the CDG command requires a screen update, a local array of pixels is
# updated to reflect the new graphic information. Rather than update
# directly to the screen for every command, updates are cached and
# output to the screen a certain number of times per second
# (configurable). Performing the scaling and blitting required for
# screen updates might consume a lot of CPU horsepower, so we reduce
# the load further by dividing the screen into 24 segments. Only those
# segments that have changed are scaled and blitted. If the user
# resizes the window or we get a full-screen modification, the entire
# screen is updated, but during normal CD+G operation only a small
# number of segments are likely to be changed at update time.
#
# NOTE: Pygame does not currently support querying the length
# of an MP3 track, therefore the GetLength() method is not
# currently implemented.
#
# Here follows a description of the important data stored by
# the class:
#
# CdgPacketReader.__cdgColourTable[]
# Store the colours for each colour index (0-15).
# These are set using the load colour look up table commands.
#
# CdgPacketReader.__cdgSurfarray[300][216]
# Surfarray object containing pixel colours for the full 300x216 screen.
# The border area is not actually displayed on the screen, however we
# need to store the pixel colours there as they are set when Scroll
# commands are used. This stores the actual pygame colour value, not
# indeces into our colour table.
#
# CdgPacketReader.__cdgPixelColours[300][216]
# Store the colour index for every single pixel. The values stored
# are indeces into our colour table, rather than actual pygame
# colour representations. It's unfortunate that we need to store 
# all this data, when in fact the pixel colour is available from
# cdgSurfarray, but we need it for the Tile Block XOR command.
# The XOR command performs an XOR of the colour index currently
# at the pixel, with the new colour index. We therefore need to
# know the actual colour index at that pixel - we can't do a 
# get_at() on the screen, or look in cdgSurfarray, and map the RGB
# colour back to a colour index because some CDG files have the 
# same colour in two places in the table, making it impossible to
# determine which index is relevant for the XOR.
#
# CdgPacketReader.__cdgPresetColourIndex 
# Preset Colour (index into colour table)
#
# CdgPacketReader.__cdgPresetColourIndex 
# Border Colour (index into colour table)
#
# CdgPacketReader.__updatedTiles
# Bitmask to mark which screen segments have been updated.
# This is used to reduce the amount of effort required in
# scaling the output video. This is an expensive operation
# which must be done for every screen update so we divide
# the screen into 24 segments and only update those segments
# which have actually been updated.

from pykconstants import *
from pykplayer import pykPlayer
from pykenv import env
from pykmanager import manager
import sys, pygame, os, string, math, re

import _pycdgAux as aux

CDG_DISPLAY_WIDTH   = 294
CDG_DISPLAY_HEIGHT  = 204

CDG_FULL_WIDTH      = 300
CDG_FULL_HEIGHT     = 216

# Screen tile positions
# The viewable area of the screen (294x204) is divided into 24 tiles
# (6x4 of 49x51 each). This is used to only update those tiles which
# have changed on every screen update, thus reducing the CPU load of
# screen updates. A bitmask of tiles requiring update is held in
# cdgPlayer.UpdatedTiles.  This stores each of the 4 columns in
# separate bytes, with 6 bits used to represent the 6 rows.
TILES_PER_ROW           = 6
TILES_PER_COL           = 4
TILE_WIDTH              = CDG_DISPLAY_WIDTH / TILES_PER_ROW
TILE_HEIGHT             = CDG_DISPLAY_HEIGHT / TILES_PER_COL

# cdgPlayer Class
class cdgPlayer(pykPlayer):
    # Initialise the player instace
    def __init__(self, fileName, errorNotifyCallback=None, doneCallback=None):
        pykPlayer.__init__(self, fileName, errorNotifyCallback, doneCallback)
                
        # Allow for calls through tab-completion, where we will
        # get just a '.' and not the '.cdg' extension
        if self.FileName[len(self.FileName)-1] == '.':
            self.FileName = self.FileName + 'cdg'
                    
        # Check the CDG file exists
        if not os.path.isfile(self.FileName):
            ErrorString = "No such file: " + self.FileName
            self.ErrorNotifyCallback (ErrorString)
            raise 'NoSuchFile'

        # With the nomusic option no music will be played.
        self.SoundFileName = None
        if manager.options.nomusic == False:
            # Check there is a matching mp3 or ogg file.  Check extensions
            # in the following order.
            validexts = [
                'wav', 'ogg', 'mp3'
            ]

            # Get the list of all files with the same basename, but any
            # extension.
            path, file = os.path.split ((self.FileName[:-3]))
            pattern = re.compile (re.escape(file))
            fileList = [filename for filename in os.listdir(path) if pattern.match(filename)] 

            # Convert them to lowercase for a case-insensitive search (but
            # keep the original case files around too).
            lowerFileList = map(lambda s: s.lower(), fileList)
            matched = 0
            for ext in validexts:
                consider = (file + ext).lower()
                try:
                    i = lowerFileList.index(consider)
                except:
                    continue

                # We found a match!
                self.SoundFileName = os.path.join(path, fileList[i])
                matched = 1
                break

            if not matched:
                ErrorString = "There is no mp3 or ogg file to match " + self.FileName
                self.ErrorNotifyCallback (ErrorString)
                raise 'NoSoundFile'

        # Handle a bug in pygame (pre-1.7) which means that the position
        # timer carries on even when the song has been paused.
        self.pauseOffsetTime = 0

        manager.InitPlayer(self)
        manager.OpenDisplay()
        manager.display.fill((0, 0, 0))

        # A working surface for blitting tiles, one at a time.
        self.workingTile = pygame.Surface((TILE_WIDTH, TILE_HEIGHT),
                                          0, manager.display)

        # A surface that contains the set of all tiles as they are to
        # be assembled onscreen.  This surface is kept at the original
        # scale, then zoomed to display size.  It is only used if
        # options.zoom_mode == 'soft'.
        self.workingSurface = pygame.Surface((CDG_DISPLAY_WIDTH, CDG_DISPLAY_HEIGHT),
                                             pygame.HWSURFACE,
                                             manager.display)

        self.borderColour = None
        self.computeDisplaySize()

        # Open the cdg and sound files
        self.packetReader = aux.CdgPacketReader(self.FileName, self.workingTile)
        
        if manager.options.nomusic == False:
            audioProperties = self.getAudioProperties(self.SoundFileName)
            manager.OpenAudio(suggestedProperties = (audioProperties))

            pygame.mixer.music.load(self.SoundFileName)

            # Set an event for when the music finishes playing
            pygame.mixer.music.set_endevent(pygame.USEREVENT)

            # Account for the size of the playback buffer in the lyrics
            # display.  Assume that the buffer will be mostly full.  On a
            # slower computer that's struggling to keep up, this may not
            # be the right amount of delay, but it should usually be
            # pretty close.
            self.InternalOffsetTime = manager.GetAudioBufferMS()
        else:
            self.InternalOffsetTime = 0
            
        # Set the CDG file at the beginning
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = self.curr_pos = 0
        self.PlayTime = 0
        self.PlayStartTime = 0

        # Some session-wide constants.
        self.ms_per_update = (1000.0 / manager.options.fps)        

    def doPlay(self):
        if manager.options.nomusic == False:
            pygame.mixer.music.play()
        else:
            self.PlayStartTime = pygame.time.get_ticks()

    # Pause the song - Use Pause() again to unpause
    def doPause(self):
        if manager.options.nomusic == False:
            pygame.mixer.music.pause()
            self.PauseStartTime = self.GetPos()
        else:
            self.PlayTime = pygame.time.get_ticks() - self.PlayStartTime

    def doUnpause(self):
        if manager.options.nomusic == False:
            self.pauseOffsetTime = self.pauseOffsetTime + (self.GetPos() - self.PauseStartTime)
            pygame.mixer.music.unpause()
        else:
            self.PlayStartTime = pygame.time.get_ticks() - self.PlayTime

    # you must call Play() to restart. Blocks until pygame is initialised
    def doRewind(self):
        # Reset the state of the packet-reading thread
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = 0
        self.PlayTime = 0
        self.PlayStartTime = 0
        # No need for the Pause() fix anymore
        self.pauseOffsetTime = 0
        # Move file pointer to the beginning of the file
        self.packetReader.Rewind()

        if manager.options.nomusic == False:
            # Actually stop the audio
            pygame.mixer.music.rewind()
            pygame.mixer.music.stop()

    # Get the current time (in milliseconds). Blocks if pygame is
    # not initialised yet.
    def GetPos(self):
        if manager.options.nomusic == False:
            return pygame.mixer.music.get_pos()
        else:
            if self.State == STATE_PLAYING:
                return pygame.time.get_ticks() - self.PlayStartTime
            else:
                return self.PlayTime

    def SetupOptions(self):
        """ Initialise and return optparse OptionParser object,
        suitable for parsing the command line options to this
        application. """

        parser = pykPlayer.SetupOptions(self, usage = "%prog [options] <CDG file>")

        # Remove irrelevant options.
        parser.remove_option('--font-scale')
        
        return parser


    def shutdown(self):
        # This will be called by the pykManager to shut down the thing
        # immediately.
        pygame.mixer.music.stop()
        pykPlayer.shutdown(self)

    def doStuff(self):
        pykPlayer.doStuff(self)
        
        # Check whether the songfile has moved on, if so
        # get the relevant CDG data and update the screen.
        if self.State == STATE_PLAYING:
            self.curr_pos = self.GetPos() - self.InternalOffsetTime - self.UserOffsetTime - self.pauseOffsetTime

            self.cdgPacketsDue = int((self.curr_pos * 300) / 1000)
            numPackets = self.cdgPacketsDue - self.cdgReadPackets
            if numPackets > 0:
                if not self.packetReader.DoPackets(numPackets):
                    # End of file.
                    print "End of file on cdg."
                    self.Close()
                self.cdgReadPackets += numPackets

            # Check if any screen updates are now due.
            if (self.curr_pos - self.LastPos) > self.ms_per_update:
                self.cdgDisplayUpdate()
                self.LastPos = self.curr_pos

    def handleEvent(self, event):
        pykPlayer.handleEvent(self, event)

    def doResize(self, newSize):
        self.computeDisplaySize()
    
        if self.borderColour != None:
            manager.display.fill(self.borderColour)

        self.packetReader.MarkTilesDirty()

    def computeDisplaySize(self):
        """ Figures out what scale and placement to use for blitting
        tiles to the screen.  This must be called at startup, and
        whenever the window size changes. """
        
        winWidth, winHeight = manager.displaySize

        # Compute an appropriate uniform scale to letterbox the image
        # within the window
        scale = min(float(winWidth) / CDG_DISPLAY_WIDTH,
                    float(winHeight) / CDG_DISPLAY_HEIGHT)
        if manager.options.zoom_mode == 'none':
            scale = 1
        elif manager.options.zoom_mode == 'int':
            if scale < 1:
                scale = 1.0/math.ceil(1.0/scale)
            else:
                scale = int(scale)
        self.displayScale = scale
        
        scaledWidth = int(scale * CDG_DISPLAY_WIDTH)
        scaledHeight = int(scale * CDG_DISPLAY_HEIGHT)

        # And the center of the display after letterboxing.
        self.displayRowOffset = (winWidth - scaledWidth) / 2
        self.displayColOffset = (winHeight - scaledHeight) / 2

        # Calculate the scaled width and height for each tile
        if manager.options.zoom_mode == 'quick' or manager.options.zoom_mode == 'int':
            self.displayTileWidth = scaledWidth / TILES_PER_ROW
            self.displayTileHeight = scaledHeight / TILES_PER_COL
        else:
            self.displayTileWidth = CDG_DISPLAY_WIDTH / TILES_PER_ROW
            self.displayTileHeight = CDG_DISPLAY_HEIGHT / TILES_PER_COL

    def getAudioProperties(self, filename):
        """ Attempts to determine the samplerate, etc., from the
        specified filename.  It would be nice to know this so we can
        configure the audio hardware to the same properties, to
        minimize run-time resampling. """

        # Ideally, SDL would tell us this (since it knows!), but
        # SDL_mixer doesn't provide an interface to query this
        # information, so we have to open the soundfile separately and
        # try to figure it out ourselves.

        basename, ext = os.path.splitext(filename)
        ext = ext.lower()

        audioProperties = None
        if ext == '.mp3':
            audioProperties = self.getMp3AudioProperties(filename)

        if audioProperties == None:
            # We don't know how to determine the audio properties from
            # this file.  Punt; almost all CD rips will be the
            # following properties.
            audioProperties = (44100, -16, 2)

        return audioProperties

    def getMp3AudioProperties(self, filename):
        """ Attempts to determine the samplerate, etc., from the
        specified filename, which is known to be an mp3 file. """

        # Hopefully, we have MP3Info.py available.
        try:
            import MP3Info
            m = MP3Info.MPEG(open(filename, 'rb'))
        except:
            return None

        channels = 1
        if 'stereo' in m.mode:
            channels = 2

        audioProperties = (m.samplerate, -16, channels)
        return audioProperties

    # Actually update/refresh the video output
    def cdgDisplayUpdate(self):
        # This routine is responsible for taking the unscaled output
        # pixel data from self.cdgSurfarray, scaling it and blitting
        # it to the actual display surface. The viewable area of the
        # unscaled surface is 294x204 pixels.  Because scaling and
        # blitting are heavy operations, we divide the screen into 24
        # tiles, and only scale and blit those tiles which have been
        # updated recently.  The CdgPacketReader class
        # (self.packetReader) is responsible for keeping track of
        # which areas of the screen have been modified.

        # There are four different approaches for blitting tiles onto
        # the display:

        # options.zoom_mode == 'none':
        #   No scaling.  The CDG graphics are centered within the
        #   display.  When a tile is dirty, it is blitted directly to
        #   manager.display.  After all dirty tiles have been blitted,
        #   we then use display.update to flip only those rectangles
        #   on the screen that have been blitted.

        # options.zoom_mode = 'quick':
        #   Trivial scaling.  Similar to 'none', but each tile is
        #   first scaled to its target scale using
        #   pygame.transform.scale(), which is quick but gives a
        #   pixelly result.  The scaled tile is then blitted to
        #   manager.display.

        # options.zoom_mode = 'int':
        #   The same as 'quick', but the scaling is constrained to be
        #   an integer multiple or divisor of its original size, which
        #   may reduce artifacts somewhat.

        # options.zoom_mode = 'soft':
        #   Antialiased scaling.  We blit all tiles onto
        #   self.workingSurface, which is maintained as the non-scaled
        #   version of the CDG graphics, similar to 'none'.  Then,
        #   after all dirty tiles have been blitted to
        #   self.workingSurface, we use pygame.transform.rotozoom() to
        #   make a nice, antialiased scaling of workingSurface to
        #   manager.display, and then flip the whole display.  (We
        #   can't scale and blit the tiles one a time in this mode,
        #   since that introduces artifacts between the tile edges.)

        borderColour = self.packetReader.GetBorderColour()
        if borderColour != self.borderColour:
            # When the border colour changes, blit the whole screen
            # and redraw it.
            self.borderColour = borderColour
            if borderColour != None:
                manager.display.fill(borderColour)
                self.packetReader.MarkTilesDirty()

        dirtyTiles = self.packetReader.GetDirtyTiles()
        if not dirtyTiles:
            # If no tiles are dirty, don't bother.
            return

        # List of update rectangles (in scaled output window)
        rect_list = []

        # Scale and blit only those tiles which have been updated
        for row, col in dirtyTiles:
            self.packetReader.FillTile(self.workingTile, row, col)

            if manager.options.zoom_mode == 'none':
                # The no-scale approach.
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                manager.display.blit(self.workingTile, rect)
                rect_list.append(rect)

            elif manager.options.zoom_mode == 'quick' or manager.options.zoom_mode == 'int':
                # The quick-scale approach.
                scaled = pygame.transform.scale(self.workingTile, (self.displayTileWidth,self.displayTileHeight))
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                manager.display.blit(scaled, rect)
                rect_list.append(rect)

            else:
                # The soft-scale approach.
                self.workingSurface.blit(self.workingTile, (self.displayTileWidth * row, self.displayTileHeight * col))

        if manager.options.zoom_mode == 'soft':
            # Now scale and blit the whole screen.
            scaled = pygame.transform.rotozoom(self.workingSurface, 0, self.displayScale)
            manager.display.blit(scaled, (self.displayRowOffset, self.displayColOffset))
            pygame.display.flip()
        elif len(rect_list) < 24:
            # Only update those areas which have changed
            pygame.display.update(rect_list)
        else:
            pygame.display.flip()

def defaultErrorPrint(ErrorString):
    print (ErrorString)

# Can be called from the command line with the CDG filepath as parameter
def main():
    player = cdgPlayer(None)
    player.Play()
    manager.WaitForPlayer()

if __name__ == "__main__":
    sys.exit(main())
    #import profile
    #result = profile.run('main()', 'pycdg.prof')
    #sys.exit(result)
    
