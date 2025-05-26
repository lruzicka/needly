#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2018, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Lukáš Růžička <lruzicka@redhat.com>

import tkinter as tk
import io
import os
import json
import sys
import libvirt
from tkinter import ttk
from tkinter import filedialog, messagebox
from PIL import Image

class Application:
    """ Hold the GUI frames and widgets, as well as the handling in the GUI. """
    def __init__(self):
        self.toplevel = tk.Tk()
        self.toplevel.title("Python Needle Editor for openQA (version 2.5.93)")
        self.toplevel.minsize(1024, 860)
        self.toplevel.grid_columnconfigure(0, weight=1)
        self.toplevel.grid_rowconfigure(0, weight=1)
        self.createMenu()
        # Map keys to the application
        self.toplevel.bind("<Control-d>", self.readImages)
        self.toplevel.bind("<Control-m>", self.modifyArea)
        self.toplevel.bind("<Control-g>", self.showArea)
        self.toplevel.bind("<Control-n>", self.nextImage)
        self.toplevel.bind("<Control-a>", self.addAreaToNeedle)
        self.toplevel.bind("<Control-r>", self.removeAreaFromNeedle)
        self.toplevel.bind("<Control-i>", self.startClickPointSetting)
        self.toplevel.bind("<Control-p>", self.prevImage)
        self.toplevel.bind("<Control-s>", self.createNeedle)
        self.toplevel.bind("<Control-o>", self.selectFile)
        self.toplevel.bind("<Control-q>", self.wrapQuit)
        self.toplevel.bind("<Control-x>", self.renameFile)
        self.toplevel.bind("<Control-b>", self.showConnectVM)
        self.toplevel.bind("<Control-t>", self.takeScreenshot)
        self.toplevel.bind("<Control-k>", self.showDebugJson)
        # Initiate the main frame of the application.
        self.frame = tk.Frame(self.toplevel)
        self.frame.grid()
        self.frame.grid_columnconfigure(0, weight=3)
        self.frame.grid_columnconfigure(1, weight=0)
        self.frame.grid_rowconfigure(0, weight=1)

        self.textJson = None # Widget for JSON output debugging
        self.buildWidgets()
        self.images = [] # List of images to be handled.
        self.needleCoordinates = [0, 0, 0, 0] # Coordinates of the needle area
        self.directory = "" # Active working directory
        self.areaRectangle = None # The red frame around the area
        self.areaClickCircle = None # The green circle around a click area
        self.needle = needleData({"properties":[], "tags":[], "area":[]}) # The Needle object
        self.area = None # The active needle area
        self.imageName = None # The name of the active image
        self.handler = None # The file reader and writer object
        self.imageIndex = 0 # Index of current image
        self.kvm = None # Connection to KVM hypervisor
        self.virtualMachine = None # Holds the name of the connected virtual machine
        self.recordingClickPoint = False # Whether in click point recording mode

    def createMenu(self):
        self.menu = tk.Menu(self.toplevel)
        # Define the File submenu
        self.menuFile = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menuFile, label='File')
        self.menuFile.add_command(label='Open file', accelerator='Ctrl-O', command=self.selectFile)
        self.menuFile.add_command(label='Open directory', accelerator='Ctrl-D', command=self.readImages)
        self.menuFile.add_command(label='Save', accelerator='Ctrl-S', command=self.createNeedle)
        self.menuFile.add_separator()
        self.menuFile.add_command(label='Load next', accelerator='Ctrl-N', command=self.nextImage)
        self.menuFile.add_command(label='Load previous', accelerator='Ctrl-P', command=self.prevImage)
        self.menuFile.add_command(label='Set name from tag', accelerator='Ctrl-X', command=self.renameFile)
        self.menuFile.add_separator()
        self.menuFile.add_command(label='Quit', accelerator='Ctrl-Q', command=self.wrapQuit)
        # Define the Area submenu
        self.menuArea = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menuArea, label='Area')
        self.menuArea.add_command(label='Add area', accelerator='Ctrl-A', command=self.addAreaToNeedle)
        self.menuArea.add_command(label='Remove area', accelerator='Ctrl-R', command=self.removeAreaFromNeedle)
        self.menuArea.add_command(label='Go to next area', accelerator='Ctrl-G', command=self.showArea)
        self.menuArea.add_command(label='Modify area', accelerator='Ctrl-M', command=self.modifyArea)
        self.menuArea.add_command(label='Set click point', accelerator='Ctrl-I', command=self.startClickPointSetting)
        # Define the VM submenu
        self.menuVm = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menuVm, label='vMachine')
        self.menuVm.add_command(label='Connect VM', accelerator='Ctrl-B', command=self.showConnectVM)
        self.menuVm.add_command(label='Take screenshot', accelerator='Ctrl-T', command=self.takeScreenshot)
        # Register the menu in the top level widget.
        self.toplevel['menu'] = self.menu

    def run(self):
        """ Starts the mainloop of the application. """
        self.toplevel.mainloop()

    def acceptCliChoice(self, path):
        """Opens an image for editing when passed as a CLI argument upon starting the editor."""
        if self.loadImageAndNeedle(path):
            self.images = [self.imageName]
            self.imageIndex = 0

    def loadImageAndNeedle(self, filePath):
        """Load and display both a image an its associated needle data.

        If no JSON file exists new needle data is created and a default area shown.

        :param str filePath: The path to either the PNG or JSON
        :return: Whether the image was successfully loaded
        :rtype: bool
        """
        self.directory = os.path.dirname(filePath)
        filename = os.path.basename(filePath)
        root, extension = os.path.splitext(filePath)
        if extension.lower() == ".png":
            imagePath = filePath
        elif extension.lower() == ".json":
            imagePath = f"{root}.png"
        else:
            messagebox.showerror("Error", "File needs to be a PNG or JSON")
            return False

        if not os.path.exists(imagePath):
            messagebox.showerror("Error", f"Image not found: {imagePath}")
            return False

        self.imageName = filename
        # Ensure the image is displayed before any areas are rendered
        self.displayImage(imagePath)

        jsonFilename = f"{root}.json"

        # If a JSON file exists load it, otherwise reset state
        if os.path.exists(jsonFilename):
            self.loadNeedle(jsonFilename)
        else:
            self.needle = needleData({"properties":[], "tags":[], "area":[]})
            # Prefill the tag field from the file name.
            tag, _ = os.path.splitext(filename)
            self.textField.delete("1.0", "end")
            self.textField.insert("end", tag)

        # Add a default area if creating new or opening needle with no areas
        if not self.needle.haveCurrentArea():
            self.addAreaToNeedle()

        return True

    def buildWidgets(self):
        """Construct GUI"""

        self.picFrame = tk.Frame(self.frame)
        self.picFrame.grid(row=0, column=0)
        self.picFrame.grid_columnconfigure(0, weight=5)
        self.picFrame.grid_columnconfigure(1, weight=0)
        self.picFrame.grid_rowconfigure(0, weight=5)
        self.picFrame.grid_rowconfigure(1, weight=0)

        self.xscroll = tk.Scrollbar(self.picFrame, orient='horizontal')
        self.xscroll.grid(row=1, column=0, sticky="nswe")
        self.xscroll.grid_columnconfigure(0, weight=1)
        self.xscroll.grid_rowconfigure(0, weight=1)

        self.yscroll = tk.Scrollbar(self.picFrame, orient='vertical')
        self.yscroll.grid(row=0, column=1, sticky="nswe")
        self.yscroll.grid_columnconfigure(0, weight=1)
        self.yscroll.grid_rowconfigure(0, weight=1)

        self.pictureField = tk.Canvas(self.picFrame, height=769, width=1025, xscrollcommand=self.xscroll.set, yscrollcommand=self.yscroll.set)
        self.pictureField.grid(row=0, column=0)
        self.pictureField.grid_columnconfigure(0, weight=1)
        self.pictureField.grid_rowconfigure(0, weight=1)
        self.pictureField.config(scrollregion=self.pictureField.bbox('ALL'))
        # Bind picture specific keys
        self.pictureField.bind("<Button 1>", self.mouseDown)
        self.pictureField.bind("<B1-Motion>", self.redrawArea)
        self.pictureField.bind("<ButtonRelease-1>", self.mouseUp)
        self.pictureField.bind("<Up>", self.resizeArea)
        self.pictureField.bind("<Down>", self.resizeArea)
        self.pictureField.bind("<Left>", self.resizeArea)
        self.pictureField.bind("<Right>", self.resizeArea)

        self.xscroll.config(command=self.pictureField.xview)
        self.yscroll.config(command=self.pictureField.yview)

        self.jsonFrame = tk.Frame(self.frame, padx=10)
        self.jsonFrame.grid(row=0, column=1, sticky="news")

        self.nameLabel = tk.Label(self.jsonFrame, text="Filename:")
        self.nameLabel.grid(row=0, column=0, sticky="w")

        self.nameEntry = tk.Entry(self.jsonFrame)
        self.nameEntry.grid(row=1, column=0, sticky="ew")

        self.propLabel = tk.Label(self.jsonFrame, text="Properties:")
        self.propLabel.grid(row=2, column=0, sticky="w")

        self.propText = tk.Text(self.jsonFrame, width=30, height=4)
        self.propText.grid(row=3, column=0, sticky="ew")

        areaFrame = tk.LabelFrame(self.jsonFrame, text="Area", padx=5, pady=5)
        areaFrame.grid(row=4, column=0, sticky="ew")

        self.needleUL = tk.Label(areaFrame, text="Coordinates:")
        self.needleUL.grid(row=0, column=0, columnspan=2, sticky="w")

        self.axLabel = tk.Label(areaFrame, text="X1:")
        self.axLabel.grid(row=1, column=0, sticky="w")

        self.axEntry = tk.Entry(areaFrame, width=5)
        self.axEntry.grid(row=1, column=1, sticky="w")

        self.ayLabel = tk.Label(areaFrame, text="Y1:")
        self.ayLabel.grid(row=1, column=2, sticky="w")

        self.ayEntry = tk.Entry(areaFrame, width=5)
        self.ayEntry.grid(row=1, column=3, sticky="w")

        self.widthLabel = tk.Label(areaFrame, text="Width:")
        self.widthLabel.grid(row=1, column=4, sticky="w")

        self.widthEntry = tk.Entry(areaFrame, width=5)
        self.widthEntry.grid(row=1, column=5, sticky="w")
        self.widthEntry.config(state="readonly")

        self.bxLabel = tk.Label(areaFrame, text="X2:")
        self.bxLabel.grid(row=2, column=0, sticky="w")

        self.bxEntry = tk.Entry(areaFrame, width=5)
        self.bxEntry.grid(row=2, column=1, sticky="w")

        self.byLabel = tk.Label(areaFrame, text="Y2:")
        self.byLabel.grid(row=2, column=2, sticky="w")

        self.byEntry = tk.Entry(areaFrame, width=5)
        self.byEntry.grid(row=2, column=3, sticky="w")

        self.heightLabel = tk.Label(areaFrame, text="Height:")
        self.heightLabel.grid(row=2, column=4, sticky="w")

        self.heightEntry = tk.Entry(areaFrame, width=5)
        self.heightEntry.grid(row=2, column=5, sticky="w")
        self.heightEntry.config(state="readonly")

        self.listLabel = tk.Label(self.jsonFrame, text="Area type:")
        self.listLabel.grid(row=6, column=0, sticky="w")
        self.listLabel = tk.Label(areaFrame, text="Type:")
        self.listLabel.grid(row=3, column=0, columnspan=6, sticky="w")

        self.typeList = tk.Spinbox(areaFrame, values=["match","ocr","exclude"])
        self.typeList.grid(row=4, column=0, columnspan=6, sticky="ew")

        self.matchLabel = tk.Label(areaFrame, text="Match level:")
        self.matchLabel.grid(row=5, column=0, columnspan=6, sticky="w")

        self.matchEntry = tk.Entry(areaFrame, width=30)
        self.matchEntry.grid(row=6, column=0, columnspan=6, sticky="ew")

        pointLabel = tk.Label(areaFrame, text="Click point:")
        pointLabel.grid(row=7, column=0, columnspan=6, sticky="w")

        xLabel = tk.Label(areaFrame, text="X:")
        xLabel.grid(row=8, column=0, sticky="w")

        self.pointxEntry = tk.Entry(areaFrame, width=5)
        self.pointxEntry.grid(row=8, column=1, sticky="w")

        yLabel = tk.Label(areaFrame, text="Y:")
        yLabel.grid(row=8, column=2, sticky="w")

        self.pointyEntry = tk.Entry(areaFrame, width=5)
        self.pointyEntry.grid(row=8, column=3, sticky="w")

        self.areaFrame = areaFrame

        self.textLabel = tk.Label(self.jsonFrame, text="Tags:")
        self.textLabel.grid(row=5, column=0, sticky="w")

        self.textField = tk.Text(self.jsonFrame, width=30, height=3)
        self.textField.grid(row=6, column=0, sticky="ew")

        self.vmLabel = tk.Label(self.jsonFrame, text="VM connection:")
        self.vmLabel.grid(row=7, column=0, sticky="w")

        self.vmEntry = tk.Entry(self.jsonFrame, width=30)
        self.vmEntry.grid(row=8, column=0, sticky="ew")
        self.vmEntry.insert("end","Not connected")
        self.vmEntry.config(state="readonly")

    # This serves as a wrapper for key bindings that were not able to invoke
    def wrapQuit(self, event=None):
        self.frame.quit()

    def returnPath(self, image):
        """Create a full path from working directory and image name."""
        return os.path.join(self.directory, image)

    def readImages(self, event=None):
        """Read PNG images from the given directory and create a list of their names."""
        self.directory = filedialog.askdirectory()
        if not self.directory:
            print("No directory selected?")
            return

        print(self.directory)
        self.images = []
        for file in os.listdir(self.directory):
            if file.lower().endswith(".png"):
                self.images.append(file)

        if not self.images:
            messagebox.showerror("Error", "Found no images the selected directory.")
        else:
            if len(self.images) == 1:
                messagebox.showinfo("Found images", "Found 1 image in the selected directory.")
            else:
                messagebox.showinfo("Found images", f"Found {len(self.images)} images in the selected directory.")

            if self.loadImageAndNeedle(self.returnPath(self.images[0])):
                self.imageIndex = 0

    def selectFile(self, event=None):
        """Reads in an image file and shows it for editing."""
        openFile = filedialog.askopenfile()
        if openFile and self.loadImageAndNeedle(openFile.name):
            self.images = [self.imageName]
            self.imageIndex = 0

    def displayImage(self, path):
        """Display image on the canvas."""
        self.picture = Image.open(path)
        self.picsize = (self.picture.width,self.picture.height)
        scrollregion = f"0 0 {self.picsize[0]} {self.picsize[1]}"
        self.pictureField.config(width=self.picsize[0], height=self.picsize[1], xscrollcommand=self.xscroll.set, yscrollcommand=self.yscroll.set, scrollregion=scrollregion)
        self.image = tk.PhotoImage(file=path)
        self.background = self.pictureField.create_image((1, 1), image=self.image, anchor='nw')
        self.nameEntry.config(state="normal")
        self.nameEntry.delete(0, "end")
        self.nameEntry.insert("end", self.imageName)
        self.nameEntry.config(state="readonly")
        self.pictureField.focus_set()

    def nextImage(self, event=None):
        """Display next image on the list."""
        if not self.images:
            messagebox.showerror("Error", "No images are loaded. Select an image first.")
            return

        self.imageIndex += 1
        if self.imageIndex >= len(self.images):
            self.imageIndex = 0

        imageName = self.images[self.imageIndex]
        self.loadImageAndNeedle(self.returnPath(imageName))

    def prevImage(self, event=None):
        """Display previous image on the list."""
        if not self.images:
            messagebox.showerror("Error", "No images are loaded. Select an image first.")
            return

        self.imageIndex -= 1
        if self.imageIndex < 0:
            self.imageIndex = len(self.images) - 1

        imageName = self.images[self.imageIndex]
        self.loadImageAndNeedle(self.returnPath(imageName))

    def getCoordinates(self):
        """Read coordinates from the coordinate windows."""
        xpos = None
        apos = None
        try:
            xpos = int(self.axEntry.get())
            ypos = int(self.ayEntry.get())
            apos = int(self.bxEntry.get())
            bpos = int(self.byEntry.get())
        except ValueError:
            messagebox.showerror("Error", "Cannot operate without images.")

        if not xpos and not apos:
            self.needleCoordinates = [0, 0, 100, 200]
        else:
            self.needleCoordinates = [xpos, ypos, apos, bpos]

    def calculateSize(self, coordinates):
        """Calculate size of the area from its coordinates."""
        width = int(coordinates[2]) - int(coordinates[0])
        height = int(coordinates[3]) - int(coordinates[1])
        return [width, height]

    def showArea(self, event=None):
        """Load area and draw a rectangle around it."""
        self.clearAreaRender()
        self.area = self.needle.provideNextArea()
        try:
            self.needleCoordinates = self.area.coordinates

            self.areaRectangle = self.pictureField.create_rectangle(self.needleCoordinates, outline="red", width=2)
            self.displayCoordinates(self.needleCoordinates)
            self.typeList.delete(0, "end")
            self.typeList.insert("end", self.area.type)
            # Some needles do not have matches defined, so we must be very careful with this.
            self.matchEntry.delete(0, "end")
            if self.area.match:
                self.matchEntry.insert("end", self.area.match)

            self.pointxEntry.delete(0, "end")
            self.pointyEntry.delete(0, "end")
            if self.area.haveClickPoint():
                self.areaClickCircle = self.drawClickPoint(self.area)
                self.pointxEntry.insert("end", self.area.clickPointX)
                self.pointyEntry.insert("end", self.area.clickPointY)

            self.updateCurrentAreaLabel()
            self.stopClickPointSetting()
        except TypeError as e:
            print(f"Unexpected error displaying needle area: {e}")

    def clearAreaRender(self):
        """Clear rendering of current area and reset tracking variables."""
        if self.areaRectangle:
            self.pictureField.delete(self.areaRectangle)
            self.areaRectangle = None
        if self.areaClickCircle:
            self.pictureField.delete(self.areaClickCircle)
            self.areaClickCircle = None

    def displayCoordinates(self, coordinates):
        """Disply coordinates in the GUI"""
        self.axEntry.delete(0, "end")
        self.axEntry.insert("end", coordinates[0])
        self.ayEntry.delete(0, "end")
        self.ayEntry.insert("end", coordinates[1])
        self.bxEntry.delete(0, "end")
        self.bxEntry.insert("end", coordinates[2])
        self.byEntry.delete(0, "end")
        self.byEntry.insert("end", coordinates[3])
        size = self.calculateSize(coordinates)

        self.widthEntry.config(state="normal")
        self.widthEntry.delete(0, "end")
        self.widthEntry.insert("end", size[0])
        self.widthEntry.config(state="readonly")

        self.heightEntry.config(state="normal")
        self.heightEntry.delete(0, "end")
        self.heightEntry.insert("end", size[1])
        self.heightEntry.config(state="readonly")

    def modifyArea(self, event=None):
        """Update the information for the active needle area, including properties, tags, etc."""
        if not self.needle.haveCurrentArea():
            messagebox.showerror("Error", "You have found a bug and don't have a current area. Add an area first!")
            return

        self.getCoordinates()
        coordsChanged = self.area.updateCoordinates(self.needleCoordinates)

        self.area.type = self.typeList.get()
        self.area.match = self.matchEntry.get()

        if coordsChanged:
            # Clear click point when moving area.
            self.clearClickPoint()
        else:
            try:
                pt_x = int(self.pointxEntry.get())
                pt_y = int(self.pointyEntry.get())
            except ValueError:
                self.area.clickPointX = None
                self.area.clickPointY = None
            else:
                self.area.clickPointX = pt_x
                self.area.clickPointY = pt_y

        props = self.propText.get("1.0", "end-1c")
        if "\n" in props:
            props = props.split("\n")
        if props == "":
            props = []
        tags = self.textField.get("1.0", "end-1c")
        if "\n" in tags:
            tags = tags.split("\n")
        if tags == "":
            tags = []

        self.needle.update(self.area, tags, props)

        self.updateDebugJson()
        self.pictureField.coords(self.areaRectangle, self.needleCoordinates)

    def drawClickPoint(self, area):
        """Draw and return area click point."""
        x = area.xpos + area.clickPointX
        y = area.ypos + area.clickPointY
        minx = x - 5
        maxx = x + 5
        miny = y - 5
        maxy = y + 5
        return self.pictureField.create_oval([minx, miny, maxx, maxy], outline="chartreuse2", width=2)

    def startClickPointSetting(self, event=None):
        """Start click point setting mode."""
        self.recordingClickPoint = True
        self.pointxEntry.config(bg="chartreuse2")
        self.pointyEntry.config(bg="chartreuse2")
        if self.areaClickCircle:
            self.pictureField.delete(self.areaClickCircle)
            self.areaClickCircle = None

    def stopClickPointSetting(self):
        """Stop click point setting mode."""
        if self.recordingClickPoint:
            self.recordingClickPoint = False
            self.pointxEntry.config(bg="white")
            self.pointyEntry.config(bg="white")

    def recordClickPoint(self, event):
        """Record click point to area."""
        x = int(self.pictureField.canvasx(event.x))
        y = int(self.pictureField.canvasy(event.y))
        areaX, areaY = self.needle.updateClickPoint(x, y)
        if areaX is not None:
            self.pointxEntry.delete(0, "end")
            self.pointxEntry.insert("end", areaX)
            self.pointyEntry.delete(0, "end")
            self.pointyEntry.insert("end", areaY)
            self.area.clickPointX = areaX
            self.area.clickPointY = areaY
            if self.areaClickCircle:
                self.pictureField.delete(self.areaClickCircle)
            self.areaClickCircle = self.drawClickPoint(self.area)
        else:
            messagebox.showerror("Error", "Point outside area.")
        self.stopClickPointSetting()

    def clearClickPoint(self):
        """Clear click point from UI, sidebar and current area."""
        if not self.needle.haveCurrentArea():
            return
        self.area.clickPointX = None
        self.area.clickPointY = None
        self.pointxEntry.delete(0, "end")
        self.pointyEntry.delete(0, "end")
        if self.areaClickCircle:
            self.pictureField.delete(self.areaClickCircle)
            self.areaClickCircle = None

    def addAreaToNeedle(self, event=None):
        """Add new area to needle. The needle can have more areas."""
        newArea = areaData.getNew(*self.picsize)
        if self.needle.haveCurrentArea():
            self.modifyArea()
        self.needle.addArea(newArea.toDict())
        self.showArea()

    def updateCurrentAreaLabel(self):
        """Update current area to area frame."""
        position = self.needle.provideCurrentAreaLabel()
        self.areaFrame["text"] = f"Area {position}"

    def removeAreaFromNeedle(self, event=None):
        """Remove the active area from the needle (deletes it)."""
        self.needle.removeArea()
        if not self.needle.haveCurrentArea():
            self.addAreaToNeedle()
        self.updateDebugJson()
        self.showArea()

    def mouseDown(self, event):
        """Handle mouse down event."""
        if not self.recordingClickPoint:
            self.startArea(event)

    def mouseUp(self, event):
        """Handle mouse up event."""
        if self.recordingClickPoint:
            self.recordClickPoint(event)
        else:
            self.endArea(event)

    def startArea(self, event):
        """Get coordinates on mouse click and start drawing the rectangle from this point."""
        xpos = int(self.pictureField.canvasx(event.x))
        ypos = int(self.pictureField.canvasy(event.y))
        self.startPoint = [xpos, ypos]
        # Clear any click point immediately
        self.clearClickPoint()
        if not self.areaRectangle:
            self.areaRectangle = self.pictureField.create_rectangle(self.needleCoordinates, outline="red", width=2)

    def redrawArea(self, event):
        """Upon mouse drag update the size of the rectangle as the mouse is moving."""
        if self.recordingClickPoint:
            return
        apos = int(self.pictureField.canvasx(event.x))
        bpos = int(self.pictureField.canvasy(event.y))
        self.endPoint = [apos, bpos]
        self.needleCoordinates = self.startPoint + self.endPoint
        self.pictureField.coords(self.areaRectangle, self.needleCoordinates)

    def endArea(self, event):
        """Stop drawing the rectangle and record the coordinates to match the final size."""
        coordinates = [0, 0, 1, 1]
        xpos = self.needleCoordinates[0]
        ypos = self.needleCoordinates[1]
        apos = self.needleCoordinates[2]
        bpos = self.needleCoordinates[3]
        self.pictureField.focus_set()

        if xpos <= apos and ypos <= bpos:
            coordinates[0] = xpos
            coordinates[1] = ypos
            coordinates[2] = apos
            coordinates[3] = bpos
        elif xpos >= apos and ypos >= bpos:
            coordinates[0] = apos
            coordinates[1] = bpos
            coordinates[2] = xpos
            coordinates[3] = ypos
        elif xpos <= apos and ypos >= bpos:
            coordinates[0] = xpos
            coordinates[1] = bpos
            coordinates[2] = apos
            coordinates[3] = ypos
        elif xpos >= apos and ypos <= bpos:
            coordinates[0] = apos
            coordinates[1] = ypos
            coordinates[2] = xpos
            coordinates[3] = bpos
        self.displayCoordinates(coordinates)
        self.modifyArea()

    def resizeArea(self, event):
        self.getCoordinates()

        if event.state == 17:
            x = 0
            y = 1
            step = 1
        elif event.state == 21:
            x = 0
            y = 1
            step = 5
        elif event.state == 25:
            x = 0
            y = 1
            step = 25
        elif event.state == 24:
            x = 2
            y = 3
            step = 25
        elif event.state == 20:
            x = 2
            y = 3
            step = 5
        else:
            x = 2
            y = 3
            step = 1

        if event.keycode == 113:
            self.needleCoordinates[x] = self.needleCoordinates[x] - step
        elif event.keycode == 114:
            self.needleCoordinates[x] = self.needleCoordinates[x] + step
        elif event.keycode == 111:
            self.needleCoordinates[y] = self.needleCoordinates[y] - step
        elif event.keycode == 116:
            self.needleCoordinates[y] = self.needleCoordinates[y] + step

        self.displayCoordinates(self.needleCoordinates)
        self.pictureField.coords(self.areaRectangle, self.needleCoordinates)
        self.modifyArea()

    def loadNeedle(self, jsonFile):
        """Load the existing needle information from the file and display them in the window."""
        self.handler = fileHandler(jsonFile)
        if not self.handler.readFile():
            return
        jsonData = self.handler.provideData()
        self.needle = needleData(jsonData)
        self.clearAreaRender()
        properties = self.needle.provideProperties()
        self.propText.delete("1.0", "end")
        self.propText.insert("end", properties)
        tags = self.needle.provideTags()
        self.textField.delete("1.0", "end")
        self.textField.insert("end", tags)
        self.updateDebugJson()
        self.updateCurrentAreaLabel()
        self.showArea()

    def createNeedle(self, event=None):
        """Write out the json file for the actual image to store the needle permanently."""
        jsonData = self.needle.provideJson()
        basename, _ = os.path.splitext(self.nameEntry.get())
        filename = f"{basename}.json"
        path = self.returnPath(filename)
        if self.handler is None:
            self.handler = fileHandler(path)
        self.handler.acceptData(jsonData)
        self.handler.writeFile(path)

    def renameFile(self, event=None):
        """ Rename the needle PNG file with the top placed tag. """
        tags = self.textField.get("1.0", "end-1c").split("\n")
        future_name = tags[0]
        if not future_name and self.imageName:
            current = self.returnPath(self.imageName)
            tag = self.imageName.split('.')[0]
            self.textField.insert("end", tag)
        elif future_name and self.imageName:
            future_name = f"{future_name}.png"
            current = self.returnPath(self.imageName)
            new = os.path.join(self.directory, future_name)
            try:
                os.rename(current, new)
                self.imageName = future_name
                self.nameEntry.config(state="normal")
                self.nameEntry.delete(0, "end")
                self.nameEntry.insert("end", future_name)
                self.nameEntry.config(state="readonly")
                messagebox.showinfo("Success", "The PNG file has been renamed.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        elif not future_name:
            messagebox.showerror("Error", "No tags available to rename the file. Leaving it unchanged.")
        elif not self.imageName:
            messagebox.showerror("Error", "No image loaded. Load an image first!")

    def showConnectVM(self, event=None):
        """ Show a dialogue to connect to a VM """
        # Get the domain names from the kvm hypervisor
        domains = []
        try:
            self.kvm = libvirt.open("qemu:///session")
            # Get the names of all running domains in the hypervisor.
            domains = [x.name() for x in self.kvm.listAllDomains()]
        except libvirt.libvirtError:
            messagebox.showerror("Error", "Failed to open connection to the hypervisor.")
            return

        if not domains:
            messagebox.showerror("No domains found", "Either the hypervisor is not running or no VMs available in the qemu:///session.")
            return

        # Create the basic GUI for the dialogue
        self.connectDialogue = tk.Toplevel(self.toplevel)
        self.connectDialogue.title('Connect to a VM')
        self.cdLayout = tk.Frame(self.connectDialogue)
        self.cdLayout.grid()
        self.cdLabel = tk.Label(self.cdLayout, text='Choose a VM:', padx=10, pady=5)
        self.cdLabel.grid(row=0, column=0)
        self.connectDialogue.bind("<Return>", self.connect)
        choices = tk.StringVar()
        self.cdChooseBox = ttk.Combobox(self.cdLayout, textvariable=choices, height=3)
        self.cdChooseBox.grid(row=0, column=1)
        self.cdChooseBox['values'] = domains
        self.cdConnect = tk.Button(self.cdLayout, text="Connect", width=10, command=self.connect)
        self.cdConnect.grid(row=1, column=1)

    def connect(self, event=None):
        """ Update the status variable to let the application know about the VM. """
        selected = self.cdChooseBox.get()
        if not selected:
            messagebox.showerror("No VM selected", "Please, select one of the available VMs.")
        self.virtualMachine = selected
        self.connectDialogue.destroy()
        self.vmEntry.config(state="normal")
        self.vmEntry.delete("0", "end")
        self.vmEntry.insert("end", self.virtualMachine)
        self.vmEntry.config(state="readonly")


    def takeScreenshot(self, event=None):
        """ Take the screenshot from the running virtual machine. As only .ppm files
        are possible, use imagemagick to convert the shot into a .png file and save
        it. """
        # When no VM has been previously selected, there is no need
        # to try and take screenshots.
        if not self.virtualMachine:
            messagebox.showerror("No VM connected", "Connect a VM before you try taking screenshots from it. Use the CTRL-V key shortcut.")
        # We have the running domain connected, so let's take the shot.
        else:
            # Use the domain name to get the domain object
            domain = self.virtualMachine
            domain = self.kvm.lookupByName(domain)
            # Create a stream to the hypervisor
            stream = self.kvm.newStream()
            # Collect the available image type of the first screen
            # On a VM usually only one screen is available,
            # so we will take the first one and will not bother
            # about others.
            domain.screenshot(stream, 0)
            # The stream will be caught in an envelope
            imageData = io.BytesIO()
            # Now, let's take the data from the stream
            part_stream = stream.recv(8192)
            while part_stream != b'':
                imageData.write(part_stream)
                part_stream = stream.recv(8192)
            # Convert and save the image
            imageData.seek(0)
            image = Image.open(imageData)
            self.imageName = "screenshot.png"
            image.save(self.imageName, 'PNG')
            imageData.close()
            stream.finish()
            path = os.path.join(os.path.abspath('.'), self.imageName)
            if self.loadImageAndNeedle(path):
                self.images = [self.imageName]
                self.imageIndex = 0

    def showDebugJson(self, event):
        """Show the JSON output widget for debugging."""
        if self.textJson:
            return

        self.jsonLabel = tk.Label(self.jsonFrame, text="JSON Data:")
        self.jsonLabel.grid(row=9, column=0, sticky="w")

        self.textJson = tk.Text(self.jsonFrame, width=30, height=8)
        self.textJson.grid(row=10, column=0, sticky="ew")
        self.textJson.config(state="disabled")

        self.updateDebugJson()

    def updateDebugJson(self):
        """If the JSON output widget is shown update its contents."""
        if not self.textJson:
            return

        self.textJson.config(state="normal")
        self.textJson.delete("1.0", "end")
        json = self.needle.provideJson()
        self.textJson.insert("end", json)
        self.textJson.config(state="disabled")

#-----------------------------------------------------------------------------------------------

class fileHandler:
    def __init__(self, jsonFile):
        self.jsonData = {"properties": [],
                         "tags": [],
                         "area": []}
        self.jsonFile = jsonFile

    def readFile(self):
        """Read the json file and create the data variable with the info."""
        success = False
        try:
            with open(self.jsonFile, "r") as inFile:
                self.jsonData = json.load(inFile)
                success = True
        except FileNotFoundError:
            if self.jsonFile != "empty":
                messagebox.showerror("Error", "No needle exists. Create one.")
            else:
                messagebox.showerror("Error", "No images are loaded. Select image directory.")
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Failed to load JSON.\n\n{e}")
        return success

    def writeFile(self, jsonFile):
        """Take the data variable and write is out as a json file."""
        with open(jsonFile, "w") as outFile:
            json.dump(self.jsonData, outFile, indent=2)
        messagebox.showinfo("Info", "The needle has been written out.")

    def provideData(self):
        """Provide the json file."""
        return self.jsonData

    def acceptData(self, jsonData):
        """Update the data in data variable."""
        self.jsonData = jsonData

class needleData:
    def __init__(self, jsonData):
        self.jsonData = jsonData
        self.areas = self.jsonData["area"]
        self.areaPos = 0

    def provideJson(self):
        """Provide the json data (for the GUI)."""
        return self.jsonData

    def provideProperties(self):
        """Provide properties."""
        # Some needles do not have properties defined and they do not open in the
        # application. We will do as if properties were empty (the mostly are anyway)
        # and the field will be created in the json as we update the needle.
        try:
            properties = "\n".join(self.jsonData["properties"])
        except KeyError:
            properties = ""
        return properties

    def provideTags(self):
        """Provide tags."""
        tags = "\n".join(self.jsonData["tags"])
        return tags

    def provideNextArea(self):
        """Provide information about the active area and move pointer to the next area for future reference."""
        # Wrap around
        if self.areaPos == len(self.areas):
            self.areaPos = 0

        area = self.areas[self.areaPos]
        self.areaPos += 1
        return areaData(area)

    def update(self, area, tags, props):
        """Update all information taken from the GUI in the data variable."""
        if self.haveCurrentArea():
            self.areas[self.areaPos-1] = area.toDict()
            self.jsonData["area"] = self.areas
        else:
            messagebox.showerror("Error", "Cannot modify non-existent area. Add an area first!")

        if not isinstance(props, list):
            props = [props]
        if not isinstance(tags, list):
            tags = [tags]
        self.jsonData["properties"] = props
        self.jsonData["tags"] = tags


    def updateClickPoint(self, x, y):
        """Update click point for current needle area."""
        if len(self.areas) < self.areaPos-1:
            print("Invalid area?")
            return (None, None)
        area = self.areas[self.areaPos-1]

        xmin = area["xpos"]
        xmax = xmin + area["width"]
        ymin = area["ypos"]
        ymax = ymin + area["height"]

        if xmin <= x <= xmax and ymin <= y <= ymax:
            areaX = x - xmin
            areaY = y - ymin
            area["click_point"] = {"xpos":areaX, "ypos":areaY}
            self.areas[self.areaPos-1] = area
            self.jsonData["area"] = self.areas
            return (areaX, areaY)
        else:
            return (None, None)

    def addArea(self, area):
        """Add new area to the needle (at the end of the list)."""
        self.areas.append(area)
        self.areaPos = len(self.areas) - 1

    def removeArea(self):
        """Remove the active area from the area list."""
        try:
            self.areas.pop(self.areaPos-1)
            self.jsonData["area"] = self.areas
            self.areaPos -= 1
        except IndexError:
            messagebox.showerror("Error", "No area in the needle. Not deleting anything.")

    def provideCurrentAreaLabel(self):
        """Provide the current area label."""
        return f"{self.areaPos}/{len(self.areas)}"

    def haveCurrentArea(self):
        """Get whether we have a current area."""
        return self.areas and len(self.areas) > self.areaPos - 1


class areaData:

    xpos = -1
    ypos = -1
    width = -1
    height = -1
    coordinates = []
    type = ""
    match = None
    clickPointX = ""
    clickPointY = ""

    def __init__(self, area):
        self.xpos = area["xpos"]
        self.ypos = area["ypos"]
        self.width = area["width"]
        self.height = area["height"]
        self.coordinates = [self.xpos, self.ypos, self.xpos + self.width, self.ypos + self.height]
        self.type = area["type"]

        if "match" in area:
            self.match = area["match"]
        if "click_point" in area:
            pt = area["click_point"]
            if "xpos" in pt and "ypos" in pt:
                self.clickPointX = pt["xpos"]
                self.clickPointY = pt["ypos"]

    def haveClickPoint(self):
        """Get whether the area has a click point."""
        return self.clickPointX and self.clickPointY

    def toDict(self):
        """Get area as dict for JSON output."""
        out = {
            "xpos": self.xpos,
            "ypos": self.ypos,
            "width": self.width,
            "height": self.height,
            "type": self.type,
        }

        if self.match:
            out["match"] = self.match
        if self.haveClickPoint():
            out["click_point"] = {
                "xpos": self.clickPointX,
                "ypos": self.clickPointY,
            }
        return out

    def updateCoordinates(self, coordsArray):
        """Update coordinates, returning whether changes were made."""
        assert len(coordsArray) == 4
        updated = False

        xpos = coordsArray[0]
        if self.xpos != xpos:
            self.xpos = xpos
            updated = True
        ypos = coordsArray[1]
        if self.ypos != ypos:
            self.ypos = ypos
            updated = True

        apos = coordsArray[2]
        bpos = coordsArray[3]
        width = int(apos) - int(self.xpos)
        if self.width != width:
            self.width = width
            updated = True
        height = int(bpos) - int(self.ypos)
        if self.height != height:
            self.height = height
            updated = True
        return updated

    @staticmethod
    def getNew(imageWidth, imageHeight):
        """Create a new area in the middle of the image."""
        width = int(imageWidth/10)
        height = int(imageHeight/10)
        x = int(imageWidth/2 - width/2)
        y = int(imageHeight/2 - height/2)
        return areaData({
            "xpos": x,
            "ypos": y,
            "width": width,
            "height": height,
            "type": "match",
        })

#-----------------------------------------------------------------------------------------------

def main():
    try:
        path = sys.argv[1]
    except IndexError:
        path = None

    app = Application()

    if path is not None:
        app.acceptCliChoice(path)

    app.run()

if __name__ == "__main__":
    main()

