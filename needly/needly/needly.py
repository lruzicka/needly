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
        self.create_menu()
        # Map keys to the application
        self.toplevel.bind("<Control-d>", self.readimages)
        self.toplevel.bind("<Control-m>", self.modifyArea)
        self.toplevel.bind("<Control-g>", self.showArea)
        self.toplevel.bind("<Control-n>", self.nextImage)
        self.toplevel.bind("<Control-a>", self.addAreaToNeedle)
        self.toplevel.bind("<Control-r>", self.removeAreaFromNeedle)
        self.toplevel.bind("<Control-i>", self.startClickPointSetting)
        self.toplevel.bind("<Control-p>", self.prevImage)
        self.toplevel.bind("<Control-l>", self.loadNeedle)
        self.toplevel.bind("<Control-s>", self.createNeedle)
        self.toplevel.bind("<Control-o>", self.selectfile)
        self.toplevel.bind("<Control-q>", self.wrapquit)
        self.toplevel.bind("<Control-x>", self.renameFile)
        self.toplevel.bind("<Control-b>", self.show_connect_VM)
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
        self.imageCount = 0 # Counter for
        self.kvm = None # Connection to KVM hypervisor
        self.virtual_machine = None # Holds the name of the connected virtual machine
        self.recordingClickPoint = False # Whether in click point recording mode

    def create_menu(self):
        self.menu = tk.Menu(self.toplevel)
        # Define the File submenu
        self.menu_file = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menu_file, label='File')
        self.menu_file.add_command(label='Open file', accelerator='Ctrl-O', command=self.selectfile)
        self.menu_file.add_command(label='Open directory', accelerator='Ctrl-D', command=self.readimages)
        self.menu_file.add_separator()
        self.menu_file.add_command(label='Load next', accelerator='Ctrl-N', command=self.nextImage)
        self.menu_file.add_command(label='Load previous', accelerator='Ctrl-P', command=self.prevImage)
        self.menu_file.add_command(label='Set name from tag', accelerator='Ctrl-X', command=self.renameFile)
        self.menu_file.add_separator()
        self.menu_file.add_command(label='Quit', accelerator='Ctrl-Q', command=self.wrapquit)
        # Define the Needle submenu
        self.menu_needle = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menu_needle, label='Needle')
        self.menu_needle.add_command(label='Load', accelerator='Ctrl-L', command=self.loadNeedle)
        self.menu_needle.add_command(label='Save', accelerator='Ctrl-S', command=self.createNeedle)

        # Define the Area submenu
        self.menu_area = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menu_area, label='Area')
        self.menu_area.add_command(label='Add area', accelerator='Ctrl-A', command=self.addAreaToNeedle)
        self.menu_area.add_command(label='Remove area', accelerator='Ctrl-R', command=self.removeAreaFromNeedle)
        self.menu_area.add_command(label='Go to next area', accelerator='Ctrl-G', command=self.showArea)
        self.menu_area.add_command(label='Modify area', accelerator='Ctrl-M', command=self.modifyArea)
        self.menu_area.add_command(label='Set click point', accelerator='Ctrl-I', command=self.startClickPointSetting)
        # Define the VM submenu
        self.menu_vm = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menu_vm, label='vMachine')
        self.menu_vm.add_command(label='Connect VM', accelerator='Ctrl-B', command=self.show_connect_VM)
        self.menu_vm.add_command(label='Take screenshot', accelerator='Ctrl-T', command=self.takeScreenshot)
        # Register the menu in the top level widget.
        self.toplevel['menu'] = self.menu

    def run(self):
        """ Starts the mainloop of the application. """
        self.toplevel.mainloop()

    def acceptCliChoice(self, path):
        """Opens an image for editing when passed as a CLI argument upon starting the editor."""
        self.directory = os.path.dirname(path)
        filename = os.path.basename(path)
        if filename.endswith('.json'):
            chunks = filename.split('.')
            self.imageName = '.'.join(chunks[:-1]) + '.png'
        else:
            self.imageName = filename
        self.imageCount = 0

        # Ensure the image is displayed before any areas are rendered
        imagePath = os.path.join(self.directory, self.imageName)
        self.displayImage(imagePath)

        # If a json file is opened, we assume that we want to load the needle automatically
        # and that the needle exists, there we will open and load the needle file.
        if filename.endswith('.json'):
            self.loadNeedle()
        else:
            # If however, we start the application with the PNG file, the json needle file
            # might not exist, therefore we need to perform a test first, before we try to load
            # it.
            # If the test fails, we will at least set the tag from the filename
            # to save users some time to type. Users can edit it, later and change the file name
            # from within the application.
            jfile = os.path.join(self.directory, self.imageName)
            # Let's replace the suffix and test if the file exists.
            pre = jfile.split('.')[0]
            exists = os.path.exists(f"{pre}.json")
            # Load the needle if it exists
            if exists:
                self.loadNeedle()
            else:
                # Or just prefill the tag field from the file name.
                tag = self.imageName.split('.')[0]
                self.textField.insert("end", tag)

        # Add a default area if creating new or opening needle with zero areas
        if not self.needle.haveCurrentArea():
            self.addAreaToNeedle()

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


    def wrapopen(self): # These functions serve as wrappers for key bindings that were not able to invoke
        self.selectfile()

    def wrapquit(self, event=None):
        self.frame.quit()

    def returnPath(self, image):
        """Create a full path from working directory and image name."""
        return os.path.join(self.directory, image)

    def readimages(self, event=None):
        """Read png images from the given directory and create a list of their names."""
        self.images = []
        self.directory = filedialog.askdirectory()
        print(self.directory)
        if self.directory:
            for file in os.listdir(self.directory):
                if file.endswith(".png"):
                    self.images.append(file)
        else:
            pass
        if len(self.images) == 1:
            messagebox.showinfo("Found images", "Found 1 image in the selected directory.")
        else:
            messagebox.showinfo("Found images", "Found {} images in the selected directory.".format(len(self.images)))
        self.imageCount = 0
        try:
            self.imageName = self.images[0]
            self.displayImage(self.returnPath(self.imageName))
        except IndexError:
            pass

    def selectfile(self, event=None):
        """Reads in an image file and shows it for editing."""
        noimage = False
        try:
            path = filedialog.askopenfile().name
        except AttributeError:
            noimage = True
        if not noimage:
            self.directory = os.path.split(path)[0]
            image = os.path.split(path)[1]
            if 'json' in image:
                prefix = image.split('.')[0]
                image = prefix + '.png'
            self.imageName = image
            self.imageCount = 0
            path = os.path.join(self.directory, image)
            self.displayImage(path)

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
        self.imageCount += 1
        try:
            self.imageName = self.images[self.imageCount]
            noimage = False
        except IndexError:
            if len(self.images) != 0:
                self.imageName = self.images[0]
                self.imageCount = 0
                noimage = False
            else:
                messagebox.showerror("Error", "No images are loaded. Select an image first.")
                noimage = True
        if not noimage:
            self.pictureField.delete(self.areaRectangle)
            self.areaRectangle = None
            self.displayImage(self.returnPath(self.imageName))

    def prevImage(self, event=None):
        """Display previous image on the list."""
        self.imageCount -= 1
        try:
            self.imageName = self.images[self.imageCount]
            noimage = False
        except IndexError:
            if len(self.images) != 0:
                self.imageName = self.images[-1]
                self.imageCount = len(self.images)
                noimage = False
            else:
                messagebox.showerror("Error", "No images are loaded. Select an image first.")
                noimage = True
        if not noimage:
            self.pictureField.delete(self.areaRectangle)
            self.areaRectangle = None
            self.displayImage(self.returnPath(self.imageName))
        else:
            pass

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
        (area_x, area_y) = self.needle.updateClickPoint(x, y)
        if area_x is not None:
            self.pointxEntry.delete(0, "end")
            self.pointxEntry.insert("end", area_x)
            self.pointyEntry.delete(0, "end")
            self.pointyEntry.insert("end", area_y)
            self.area.clickPointX = area_x
            self.area.clickPointY = area_y
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
        self.showArea(None)

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

    def loadNeedle(self, event=None):
        """Load the existing needle information from the file and display them in the window."""
        if self.imageName is not None:
            jsonfile = self.returnPath(self.imageName).replace(".png", ".json")
            self.handler = fileHandler(jsonfile)
            if not self.handler.readFile():
                return
            jsondata = self.handler.provideData()
            self.needle = needleData(jsondata)
            self.clearAreaRender()
            properties = self.needle.provideProperties()
            self.propText.delete("1.0", "end")
            self.propText.insert("end", properties)
            tags = self.needle.provideTags()
            self.textField.delete("1.0", "end")
            self.textField.insert("end", tags)
            self.updateDebugJson()
            self.updateCurrentAreaLabel()
            self.showArea(None)
        else:
            messagebox.showerror("Error", "No images are loaded. Select image directory first.")

    def createNeedle(self, event=None):
        """Write out the json file for the actual image to store the needle permanently."""
        jsondata = self.needle.provideJson()
        filename = self.nameEntry.get().replace(".png", ".json")
        path = self.returnPath(filename)
        if self.handler is None:
            self.handler = fileHandler(path)
        self.handler.acceptData(jsondata)
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

    def show_connect_VM(self, event=None):
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
        self.connect_dialogue = tk.Toplevel(self.toplevel)
        self.connect_dialogue.title('Connect to a VM')
        self.cd_layout = tk.Frame(self.connect_dialogue)
        self.cd_layout.grid()
        self.cd_label = tk.Label(self.cd_layout, text='Choose a VM:', padx=10, pady=5)
        self.cd_label.grid(row=0, column=0)
        self.connect_dialogue.bind("<Return>", self.connect)
        choices = tk.StringVar()
        self.cd_choose_box = ttk.Combobox(self.cd_layout, textvariable=choices, height=3)
        self.cd_choose_box.grid(row=0, column=1)
        self.cd_choose_box['values'] = domains
        self.cd_connect = tk.Button(self.cd_layout, text="Connect", width=10, command=self.connect)
        self.cd_connect.grid(row=1, column=1)

    def connect(self, event=None):
        """ Update the status variable to let the application know about the VM. """
        selected = self.cd_choose_box.get()
        if not selected:
            messagebox.showerror("No VM selected", "Please, select one of the available VMs.")
        self.virtual_machine = selected
        self.connect_dialogue.destroy()
        self.vmEntry.config(state="normal")
        self.vmEntry.delete("0", "end")
        self.vmEntry.insert("end", self.virtual_machine)
        self.vmEntry.config(state="readonly")


    def takeScreenshot(self, event=None):
        """ Take the screenshot from the running virtual machine. As only .ppm files
        are possible, use imagemagick to convert the shot into a .png file and save
        it. """
        # When no VM has been previously selected, there is no need
        # to try and take screenshots.
        if not self.virtual_machine:
            messagebox.showerror("No VM connected", "Connect a VM before you try taking screenshots from it. Use the CTRL-V key shortcut.")
        # We have the running domain connected, so let's take the shot.
        else:
            # Use the domain name to get the domain object
            domain = self.virtual_machine
            domain = self.kvm.lookupByName(domain)
            # Create a stream to the hypervisor
            stream = self.kvm.newStream()
            # Collect the available image type of the first screen
            # On a VM usually only one screen is available,
            # so we will take the first one and will not bother
            # about others.
            domain.screenshot(stream, 0)
            # The stream will be caught in an envelope
            image_data = io.BytesIO()
            # Now, let's take the data from the stream
            part_stream = stream.recv(8192)
            while part_stream != b'':
                image_data.write(part_stream)
                part_stream = stream.recv(8192)
            # Convert and save the image
            image_data.seek(0)
            image = Image.open(image_data)
            image.save("screenshot.png", 'PNG')
            image_data.close()
            stream.finish()
            path = os.path.join(os.path.abspath('.'), 'screenshot.png')
            self.imageName = "screenshot.png"
            self.displayImage(path)
            self.textField.delete("1.0", "end")
            self.textField.insert("end", self.imageName)

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
    def __init__(self, jsonfile):
        self.jsonData = {"properties": [],
                         "tags": [],
                         "area": []}
        self.jsonfile = jsonfile

    def readFile(self):
        """Read the json file and create the data variable with the info."""
        success = False
        try:
            with open(self.jsonfile, "r") as inFile:
                self.jsonData = json.load(inFile)
                success = True
        except FileNotFoundError:
            if self.jsonfile != "empty":
                messagebox.showerror("Error", "No needle exists. Create one.")
            else:
                messagebox.showerror("Error", "No images are loaded. Select image directory.")
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Failed to load JSON.\n\n{e}")
        return success

    def writeFile(self, jsonfile):
        """Take the data variable and write is out as a json file."""
        with open(jsonfile, "w") as outFile:
            json.dump(self.jsonData, outFile, indent=2)
        messagebox.showinfo("Info", "The needle has been written out.")

    def provideData(self):
        """Provide the json file."""
        return self.jsonData

    def acceptData(self, jsondata):
        """Update the data in data variable."""
        self.jsonData = jsondata

class needleData:
    def __init__(self, jsondata):
        self.jsonData = jsondata
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
            area_x = x - xmin
            area_y = y - ymin
            area["click_point"] = {"xpos":area_x, "ypos":area_y}
            self.areas[self.areaPos-1] = area
            self.jsonData["area"] = self.areas
            return (area_x, area_y)
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
    def getNew(image_width, image_height):
        """Create a new area in the middle of the image."""
        width = int(image_width/10)
        height = int(image_height/10)
        x = int(image_width/2 - width/2)
        y = int(image_height/2 - height/2)
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

