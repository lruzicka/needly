#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 18 08:46:48 2018

@author: Lukáš Růžička (lruzicka@redhat.com)
"""

import tkinter as tk
import os
import json
import re
import sys
import subprocess
from tkinter import ttk
from tkinter import filedialog, messagebox
from PIL import Image

class Application:
    """ Hold the GUI frames and widgets, as well as the handling in the GUI. """
    def __init__(self):
        self.toplevel = tk.Tk()
        self.toplevel.title("Python Needle Editor for openQA (version 2.5)")
        self.create_menu()
        # Map keys to the application
        self.toplevel.bind("<Control-d>", self.readimages)
        self.toplevel.bind("<Control-m>", self.modifyArea)
        self.toplevel.bind("<Control-g>", self.showArea)
        self.toplevel.bind("<Control-n>", self.nextImage)
        self.toplevel.bind("<Control-a>", self.addAreaToNeedle)
        self.toplevel.bind("<Control-r>", self.removeAreaFromNeedle)
        self.toplevel.bind("<Control-p>", self.prevImage)
        self.toplevel.bind("<Control-l>", self.loadNeedle)
        self.toplevel.bind("<Control-s>", self.createNeedle)
        self.toplevel.bind("<Control-o>", self.selectfile)
        self.toplevel.bind("<Control-q>", self.wrapquit)
        self.toplevel.bind("<Control-x>", self.renameFile)
        self.toplevel.bind("<Control-v>", self.show_connect_VM)
        self.toplevel.bind("<Control-t>", self.takeScreenshot)
        # Initiate the main frame of the application.
        self.frame = tk.Frame(self.toplevel)
        self.frame.grid()
        self.buildWidgets()
        self.images = [] # List of images to be handled.
        self.needleCoordinates = [0, 0, 0, 0] # Coordinates of the needle area
        self.directory = "" # Active working directory
        self.rectangle = None # The red frame around the area
        self.needle = needleData({"properties":[], "tags":[], "area":[]}) # The Needle object
        self.imageName = None # The name of the active image
        self.handler = None # The file reader and writer object
        self.imageCount = 0 # Counter for
        self.rectangles = [] # Holder for rectangles
        self.virtual_machine = None # Holds the name of the connected virtual machine

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
        # Define the VM submenu
        self.menu_vm = tk.Menu(self.menu)
        self.menu.add_cascade(menu=self.menu_vm, label='vMachine')
        self.menu_vm.add_command(label='Connect VM', accelerator='Ctrl-V', command=self.show_connect_VM)
        self.menu_vm.add_command(label='Take screenshot', accelerator='Ctrl-T', command=self.takeScreenshot)
        # Register the menu in the top level widget.
        self.toplevel['menu'] = self.menu

    def run(self):
        """ Starts the mainloop of the application. """
        self.toplevel.mainloop()

    def acceptCliChoice(self, path):
        """Opens an image for editing when passed as a CLI argument upon starting the editor."""
        self.directory = os.path.dirname(path)
        image = os.path.basename(path)
        if '.json' in image:
            prefix = image.split('.')[0]
            image = prefix + '.png'
        self.imageName = image    
        self.imageCount = 0
        path = os.path.join(self.directory, self.imageName)
        self.displayImage(path)
        
    def buildWidgets(self):
        """Construct GUI"""
        
        self.picFrame = tk.Frame(self.frame)
        self.picFrame.grid(row=0, column=0)
                
        self.xscroll = tk.Scrollbar(self.picFrame, orient='horizontal')
        self.xscroll.grid(row=1, column=0, sticky="we")
        
        self.yscroll = tk.Scrollbar(self.picFrame, orient='vertical')
        self.yscroll.grid(row=0, column=1, columnspan=2, sticky="ns")

        self.pictureField = tk.Canvas(self.picFrame, height=800, width=1200, xscrollcommand=self.xscroll.set, yscrollcommand=self.yscroll.set)
        self.pictureField.grid(row=0, column=0)
        self.pictureField.config(scrollregion=self.pictureField.bbox('ALL'))
        # Bind picture specific keys
        self.pictureField.bind("<Button 1>", self.startArea)
        self.pictureField.bind("<B1-Motion>", self.redrawArea)
        self.pictureField.bind("<ButtonRelease-1>", self.endArea)
        self.pictureField.bind("<Up>", self.resizeArea)
        self.pictureField.bind("<Down>", self.resizeArea)
        self.pictureField.bind("<Left>", self.resizeArea)
        self.pictureField.bind("<Right>", self.resizeArea)
        
        self.xscroll.config(command=self.pictureField.xview)
        self.yscroll.config(command=self.pictureField.yview)
        
        self.jsonFrame = tk.Frame(self.frame, padx=10)
        self.jsonFrame.grid(row=0, column=2, sticky="news")

        self.nameLabel = tk.Label(self.jsonFrame, text="Filename:")
        self.nameLabel.grid(row=0, column=0, sticky="w")
        
        self.nameEntry = tk.Entry(self.jsonFrame)
        self.nameEntry.grid(row=1, column=0, sticky="ew")
        
        self.propLabel = tk.Label(self.jsonFrame, text="Properties:")
        self.propLabel.grid(row=2, column=0, sticky="w")
        
        self.propText = tk.Text(self.jsonFrame, width=30, height=4)
        self.propText.grid(row=3, column=0, sticky="ew")

        self.needleUL = tk.Label(self.jsonFrame, text="Area Coordinates:")
        self.needleUL.grid(row=4, column=0, sticky="w")

        self.coordFrame = tk.Frame(self.jsonFrame)
        self.coordFrame.grid(row=5, column=0, sticky="ew")

        self.axLable = tk.Label(self.coordFrame, text="X1:")
        self.axLable.grid(row=0, column=0, sticky="w")
        
        self.axEntry = tk.Entry(self.coordFrame, width=5)
        self.axEntry.grid(row=0, column=1, sticky="w")

        self.ayLable = tk.Label(self.coordFrame, text="Y1:")
        self.ayLable.grid(row=0, column=2, sticky="w")

        self.ayEntry = tk.Entry(self.coordFrame, width=5)
        self.ayEntry.grid(row=0, column=3, sticky="w")

        self.widthLabel = tk.Label(self.coordFrame, text="Area width:")
        self.widthLabel.grid(row=0, column=4, sticky="w")

        self.widthEntry = tk.Entry(self.coordFrame, width=5)
        self.widthEntry.grid(row=0, column=5, sticky="w")

        self.heigthLabel = tk.Label(self.coordFrame, text="Area heigth:")
        self.heigthLabel.grid(row=1, column=4, sticky="w")

        self.heigthEntry = tk.Entry(self.coordFrame, width=5)
        self.heigthEntry.grid(row=1, column=5, sticky="w")

        self.bxLable = tk.Label(self.coordFrame, text="X2:")
        self.bxLable.grid(row=1, column=0, sticky="w")

        self.bxEntry = tk.Entry(self.coordFrame, width=5)
        self.bxEntry.grid(row=1, column=1, sticky="w")

        self.byLable = tk.Label(self.coordFrame, text="Y2:")
        self.byLable.grid(row=1, column=2, sticky="w")

        self.byEntry = tk.Entry(self.coordFrame, width=5)
        self.byEntry.grid(row=1, column=3, sticky="w")

        self.listLabel = tk.Label(self.jsonFrame, text="Area type:")
        self.listLabel.grid(row=6, column=0, sticky="w")
        
        self.typeList = tk.Spinbox(self.jsonFrame, values=["match","ocr","exclude"])
        self.typeList.grid(row=7, column=0, sticky="ew")
        
        self.textLabel = tk.Label(self.jsonFrame, text="Tags:")
        self.textLabel.grid(row=8, column=0, sticky="w")
        
        self.textField = tk.Text(self.jsonFrame, width=30, height=5)
        self.textField.grid(row=9, column=0, sticky="ew")
        
        self.jsonLabel = tk.Label(self.jsonFrame, text="Json Data:")
        self.jsonLabel.grid(row=10, column=0, sticky="w")
        
        self.textJson = tk.Text(self.jsonFrame, width=30, height=10)
        self.textJson.grid(row=11, column=0, sticky="ew")

        self.needleLabel = tk.Label(self.jsonFrame, text="Areas in needle: ")
        self.needleLabel.grid(row=12, column=0, sticky="w")

        self.needleEntry = tk.Entry(self.jsonFrame, width=30)
        self.needleEntry.grid(row=13, column=0, sticky="w")

        self.vmLabel = tk.Label(self.jsonFrame, text="VM connection:")
        self.vmLabel.grid(row=14, column=0, sticky="w")
        
        self.vmEntry = tk.Entry(self.jsonFrame, width=30)
        self.vmEntry.grid(row=15, column=0, sticky="w")
        self.vmEntry.insert("end","Not connected")


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
        if noimage == False:
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
        if noimage == False:
            self.pictureField.delete(self.rectangle)
            self.rectangle = None
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
        if noimage == False:
            self.pictureField.delete(self.rectangle)
            self.rectangle = None
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
        heigth = int(coordinates[3]) - int(coordinates[1])
        return [width, heigth]
            
    def showArea(self, event=None):
        """Load area and draw a rectangle around it."""
        #self.getCoordinates()
        self.area = self.needle.provideNextArea()
        try:
            self.needleCoordinates = [self.area[0], self.area[1], self.area[2], self.area[3]]
            typ = self.area[4]
            self.rectangle = self.pictureField.create_rectangle(self.needleCoordinates, outline="red", width=2)
            self.rectangles.append(self.rectangle)
            self.displayCoordinates(self.needleCoordinates)
            self.typeList.delete(0, "end")
            self.typeList.insert("end", typ)
        except TypeError:
            for r in self.rectangles:
                self.pictureField.delete(r)


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
        self.widthEntry.delete(0, "end")
        self.widthEntry.insert("end", size[0])
        self.heigthEntry.delete(0, "end")
        self.heigthEntry.insert("end", size[1])
        
    def modifyArea(self, event=None):
        """Update the information for the active needle area, including properties, tags, etc."""
        self.getCoordinates()
        xpos = self.needleCoordinates[0]
        ypos = self.needleCoordinates[1]
        apos = self.needleCoordinates[2]
        bpos = self.needleCoordinates[3]
        typ = self.typeList.get()
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
        coordinates = [xpos, ypos, apos, bpos, typ]
        self.needle.update(coordinates, tags, props)
        self.textJson.delete("1.0", "end")
        json = self.needle.provideJson()
        self.textJson.insert("end", json)
        self.pictureField.coords(self.rectangle, self.needleCoordinates)
        
    def addAreaToNeedle(self, event=None):
        """Add new area to needle. The needle can have more areas."""
        self.needle.addArea()
        self.modifyArea(None)
        areas = self.needle.provideAreaCount()
        self.needleEntry.delete(0, "end")
        self.needleEntry.insert("end", areas)


    def removeAreaFromNeedle(self, event=None):
        """Remove the active area from the needle (deletes it)."""
        self.needle.removeArea()
        areas = self.needle.provideAreaCount()
        coordinates = [0, 0, 0, 0]
        self.displayCoordinates(coordinates)
        self.needleEntry.delete(0, "end")
        self.needleEntry.insert("end", areas)
        json = self.needle.provideJson()
        self.textJson.delete("1.0", "end")
        self.textJson.insert("end", json)
        self.pictureField.delete(self.rectangle)
        self.showArea(None)
        
    def startArea(self, event):
        """Get coordinates on mouse click and start drawing the rectangle from this point."""
        xpos = event.x
        ypos = event.y
        self.startPoint = [xpos, ypos]
        if self.rectangle == None:
            self.rectangle = self.pictureField.create_rectangle(self.needleCoordinates, outline="red", width=2)
            
    def redrawArea(self, event):
        """Upon mouse drag update the size of the rectangle as the mouse is moving."""
        apos = event.x
        bpos = event.y
        self.endPoint = [apos, bpos]
        self.needleCoordinates = self.startPoint + self.endPoint
        self.pictureField.coords(self.rectangle, self.needleCoordinates)
        
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
        self.pictureField.coords(self.rectangle, self.needleCoordinates)
        

        
    def loadNeedle(self, event=None):
        """Load the existing needle information from the file and display them in the window."""
        if self.imageName != None:
            jsonfile = self.returnPath(self.imageName).replace(".png", ".json")
            self.handler = fileHandler(jsonfile)
            self.handler.readFile()
            jsondata = self.handler.provideData()

            self.needle = needleData(jsondata)
            properties = self.needle.provideProperties()
            self.propText.delete("1.0", "end")
            self.propText.insert("end", properties)
            tags = self.needle.provideTags()
            self.textField.delete("1.0", "end")
            self.textField.insert("end", tags)
            json = self.needle.provideJson()
            self.textJson.delete("1.0", "end")
            self.textJson.insert("end", json)
            areas = self.needle.provideAreaCount()
            self.needleEntry.delete(0, "end")
            self.needleEntry.insert(0, areas)
            if self.rectangle != None:
                self.pictureField.delete(self.rectangle)
                self.rectangle = None
            self.showArea(None)
        else:
            messagebox.showerror("Error", "No images are loaded. Select image directory first.")

    def createNeedle(self, event=None):
        """Write out the json file for the actual image to store the needle permanently."""
        jsondata = self.needle.provideJson()
        filename = self.nameEntry.get().replace(".png", ".json")
        path = self.returnPath(filename)
        if self.handler == None:
            self.handler = fileHandler(path)
        self.handler.acceptData(jsondata)
        self.handler.writeFile(path)
        self.pictureField.delete(self.rectangle)
        self.rectangle = None

    def renameFile(self, event=None):
        """ Rename the needle PNG file with the top placed tag. """
        tags = self.textField.get("1.0", "end-1c").split("\n")
        future_name = tags[0]
        if future_name and self.imageName:
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
        # Create the basic GUI for the dialogue
        self.connect_dialogue = tk.Toplevel(self.toplevel)
        self.connect_dialogue.title('Connect to a VM')
        self.cd_layout = tk.Frame(self.connect_dialogue)
        self.cd_layout.grid()
        self.cd_label = tk.Label(self.cd_layout, text='Choose a VM:', padx=10, pady=5)
        self.cd_label.grid(row=0, column=0)
        self.connect_dialogue.bind("<Return>", self.connect)

        # Get the domain names from the external application (virsh)
        run = subprocess.run(['virsh', 'list'], capture_output=True)
        domains = []
        # If the virsh command fails, tell us about it.
        if run.returncode != 0:
            messagebox.showerror("Error", run.stderr.decode('utf-8'))
        # Otherwise, handle the command output to get a list of
        # running and available virtual machines.
        else:
            output = run.stdout.decode('utf-8').split('\n')
            doms = output[2:]
            for line in doms:
                try:
                    d = re.split("\s+", line)
                    d = d[2].strip()
                    domains.append(d)                    
                except IndexError:
                    break
        if len(domains) == 0:
            messagebox.showerror("No domains found", "If there is a running VM, it may not be running in the user profile. Either run in the user profile or run the application with correct privileges.")
        # Put the domain names into the Combobox widget to allow to select one of them.
        choices = tk.StringVar()
        self.cd_choose_box = ttk.Combobox(self.cd_layout, textvariable=choices, height=3)
        self.cd_choose_box.grid(row=0, column=1)
        self.cd_connect = tk.Button(self.cd_layout, text="Connect", width=10, command=self.connect)
        self.cd_connect.grid(row=1, column=1)
        self.cd_choose_box['values'] = domains

    def connect(self, event=None):
        """ Update the status variable to let the application know about the VM. """
        selected = self.cd_choose_box.get()
        if not selected:
            messagebox.showerror("No VM selected", "Please, select one of the available VMs.")
        self.virtual_machine = selected
        self.connect_dialogue.destroy()
        self.vmEntry.delete("0", "end")
        self.vmEntry.insert("end", self.virtual_machine)

        
    def takeScreenshot(self, event=None):
        """ Take the screenshot from the running virtual machine. As only .ppm files
        are possible, use imagemagick to convert the shot into a .png file and save
        it. """
        # When no VM is available for taking shots (the VM is not connected)
        if not self.virtual_machine:
            messagebox.showerror("No VM connected", "Connect a VM before you try taking screenshots from it. Use the CTRL-V key shortcut.")
        # Else do take the shot.
        else:
            domain = self.virtual_machine
            shot = subprocess.run(['virsh', 'screenshot', domain, 'screenshot.ppm'], capture_output=True)
            if shot.returncode == 0:
                convert = subprocess.run(['convert', 'screenshot.ppm', 'screenshot.png'], capture_output=True)
                if convert.returncode != 0:
                    messagebox.showerror("Conversion failed", f"Could not convert the ppm file into the target format.")   
                delete = subprocess.run(['rm', '-f', 'screenshot.ppm'], capture_output=True)
                if delete.returncode != 0:
                    messagebox.showerror("Deletion failed", "Could not delete the temporary file.")   
                path = os.path.join(os.path.abspath('.'), 'screenshot.png')
                self.imageName = 'screenshot.png'
                self.imageCount = 0
                self.displayImage(path)
                self.textField.delete("1.0", "end")
                self.textField.insert("end", self.imageName)
            
            else:
                messagebox.showerror("Error", f"The screen shot was not taken!\n{shot.stderr.decode('utf-8')}")
            

#-----------------------------------------------------------------------------------------------

class fileHandler:
    def __init__(self, jsonfile):
        self.jsonData = {"properties": [],
                         "tags": [],
                         "area": []}
        self.jsonfile = jsonfile

    def readFile(self):
        """Read the json file and create the data variable with the info."""
        try:
            with open(self.jsonfile, "r") as inFile:
                self.jsonData = json.load(inFile)
        except FileNotFoundError:
            if self.jsonfile != "empty":
                messagebox.showerror("Error", "No needle exists. Create one.")
            else:
                messagebox.showerror("Error", "No images are loaded. Select image directory.")

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
        properties = "\n".join(self.jsonData["properties"])
        return properties
    
    def provideTags(self):
        """Provide tags."""
        tags = "\n".join(self.jsonData["tags"])
        return tags
    
    def provideNextArea(self):
        """Provide information about the active area and move pointer to the next area for future reference."""
        try:
            area = self.areas[self.areaPos]
            xpos = area["xpos"]
            ypos = area["ypos"]
            wide = area["width"]
            high = area["height"]
            typ = area["type"]
            apos = xpos + wide
            bpos = ypos + high
            areaData = [xpos, ypos, apos, bpos, typ]
            self.areaPos += 1
            return areaData
        except IndexError:
            messagebox.showerror("Error", "No more area in the needle.")

    def update(self, coordinates, tags, props):
        """Update all information taken from the GUI in the data variable."""
        xpos = coordinates[0]
        ypos = coordinates[1]
        apos = coordinates[2]
        bpos = coordinates[3]
        typ = coordinates[4]
        wide = int(apos) - int(xpos)
        high = int(bpos) - int(ypos)
        area = {"xpos":xpos, "ypos":ypos, "width":wide, "height":high, "type":typ}
        if type(props) != list:
            props = [props]
        if type(tags) != list:
            tags = [tags]
        self.jsonData["properties"] = props
        self.jsonData["tags"] = tags
        
        try:
            self.areas[self.areaPos-1] = area
        except IndexError:
            messagebox.showerror("Error", "Cannot modify non-existent area. Add area first!")
        self.jsonData["area"] = self.areas
            
    def addArea(self):
        """Add new area to the needle (at the end of the list)."""
        self.areas.append("newarea")
        self.areaPos = len(self.areas)

    def removeArea(self):
        """Remove the active area from the area list."""
        try:
            deleted = self.areas.pop(self.areaPos-1)
            self.jsonData["area"] = self.areas
            self.areaPos -= 2
        except IndexError:
            messagebox.showerror("Error", "No area in the needle. Not deleting anything.")

    def provideAreaCount(self):
        """Provide the number of the areas in the needle."""
        return len(self.areas)


def main():
    """ Main application method. """

    try:
        path = sys.argv[1]
    except IndexError:
        path = None
        
    app = Application()
    
    if path != None:
        app.acceptCliChoice(path)
    
    app.run()

if __name__ == '__main__':
    main()
