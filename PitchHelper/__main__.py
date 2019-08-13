import pyaudio
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import aubio
from bs4 import BeautifulSoup
from requests import get
import wx
from pysynth_b import *
import os.path
import wave

CHUNK = 1024
RATE = 44100

class MenuWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, parent=None, title='Pitch Helper')
        self.panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.record_button = wx.Button(self.panel, label='Record')
        self.synth_button = wx.Button(self.panel, label='Open Synthesizer')

        self.sizer.Add(self.record_button, 0, wx.ALL | wx.EXPAND | wx.CENTER, 0)
        self.sizer.Add(self.synth_button, 0, wx.ALL | wx.EXPAND | wx.CENTER, 0)
        self.panel.SetSizer(self.sizer)

        self.record_button.Bind(wx.EVT_BUTTON, self.OnRecord)
        self.synth_button.Bind(wx.EVT_BUTTON, self.OnOpenSynth)

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Show()

        self.audio = None
        self.synth = None

    def OnRecord(self, event):
        self.audio = RecordWindow(self)
        self.audio.Show()

    def OnOpenSynth(self, event):
        if self.audio:
            if not self.audio.synth and not self.synth:
                self.synth = SynthWindow(self)
        else:
            if not self.synth:
                self.synth = SynthWindow(self)

    def OnClose(self, event):
        if self.audio:
            self.audio.Destroy()
        if self.synth:
            if self.synth.p:
                self.p.terminate()
            if self.synth.stream:
                self.stream.close()
            self.synth.Destroy()
        self.Destroy()

class SynthWindow(wx.Frame):
    def __init__(self, parent):

        self.stream = None
        self.p = None
        self.parent = parent

        super().__init__(parent=None, title='Synthesizer')
        self.panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.input_note = wx.TextCtrl(self.panel)
        self.play_button = wx.Button(self.panel, label='Play')
        self.play_button.Bind(wx.EVT_BUTTON, self.OnPlay)

        self.sizer.Add(self.input_note, 0, wx.ALL | wx.EXPAND | wx.CENTER, 0)
        self.sizer.Add(self.play_button, 0, wx.ALL | wx.EXPAND | wx.CENTER, 0)
        self.panel.SetSizer(self.sizer)

        #checks if .wav files for notes already exists
        #if not then creates them
        if not os.path.exists(os.getcwd() + "/Notes"):
            # create audio files for individual notes
            #scrape note names online and use them to create audio files of each note
            url = "https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies"
            page = get(url, timeout=5)
            soup = BeautifulSoup(page.content, 'html.parser')
            table = soup.find('table')
            rows = table.find_all('tr')

            notes = {}
            for row in rows:
                col = row.find_all('td')
                if(len(col) > 0):
                    if(col[2].text.isdigit()):
                        notename = col[3].text.lower().split("/")
                        for n in notename:
                            if (n != "\xa0") and ("note" not in n):
                                if ("middle" in n) or ("concert" in n):
                                    temp_n = n.split(" ")
                                    new_n = temp_n[0]
                                    notes[new_n] = col[0].text
                                else:
                                    notes[n] = col[0].text

            for note in notes:
                filename = note + ".wav"
                song = tuple([note, 1]), tuple([note, 1])
                make_wav(song, fn=filename)

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Show()

    def OnPlay(self, event):
        note = self.input_note.GetValue().lower()

        #default note octave is 4
        if not note[-1].isdigit():
            note = note + "4"

        path = os.getcwd() + "/Notes/"
        wavefile = path + note + ".wav"
        wf = wave.open(wavefile, 'rb')
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=self.p.get_format_from_width(wf.getsampwidth()),
                                  channels = wf.getnchannels(),
                                  rate = wf.getframerate(),
                                  output = True)
        data = wf.readframes(CHUNK)

        while data != b'':
            self.stream.write(data)
            data = wf.readframes(CHUNK)

        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

    def OnClose(self, event):
        self.Destroy()
        self.parent.synth = None

class RecordWindow(wx.Frame):

    def __init__(self, parent):
        self.stream = None
        self.p = None
        self.parent = parent
        self.dc = None
        self.synth = None

        super().__init__(parent=None, title='Audio Recorder')
        plt.style.use('dark_background')

        #prep input stream for audio
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paFloat32, channels=1, rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

        win_s = 4096
        hop_s = CHUNK
        self.notes_o = aubio.notes("default", win_s, hop_s, RATE)

        #prep variables for plotting
        self.xs = []
        self.ys = []

        self.fig = plt.figure()
        self.ax = plt.axes(xlim=(0,100), ylim=(0,2000))
        self.line, = self.ax.plot([], [])
        self.line.set_data(self.xs, self.ys)

        # scrape midi number to note conversion data online
        self.miditonote = {}
        url = "https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies"
        page = get(url, timeout=5)
        soup = BeautifulSoup(page.content, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')

        for row in rows:
            col = row.find_all('td')
            if(len(col) > 0):
                if col[0].text.isdigit():
                    midinumber = int(col[0].text)
                    self.miditonote[midinumber] = col[3].text

        #prep GUI
        self.panel = wx.Panel(self, size=(780,480))
        self.canvas = FigureCanvas(self.panel, -1, self.fig)

        #sizer for graph
        self.graphsizer = wx.BoxSizer(wx.VERTICAL)
        self.graphsizer.Add(self.canvas, 1, wx.TOP | wx.LEFT | wx.GROW)

        #sizer for note and audio
        self.audiosizer = wx.BoxSizer(wx.VERTICAL)
        self.notetext = wx.StaticText(self.panel, style=wx.ALIGN_LEFT)
        self.notetext.SetForegroundColour('blue')
        self.notebox = wx.StaticBox(self.panel, size=(150,50))
        self.noteboxsizer = wx.StaticBoxSizer(self.notebox, wx.VERTICAL)
        self.noteboxsizer.Add(self.notetext, 0, wx.ALIGN_LEFT)
        self.audiobutton = wx.Button(self.panel, -1, "Pause")
        self.synthbutton = wx.Button(self.panel, -1, "Open Synthesizer")
        self.audiosizer.AddSpacer(10)
        self.audiosizer.Add(self.audiobutton, 0, wx.ALIGN_CENTER | wx.ALL, border=5)
        self.audiosizer.AddSpacer(10)
        self.audiosizer.Add(self.noteboxsizer, 0, wx.ALIGN_CENTER | wx.ALL, border=5)
        self.audiosizer.AddSpacer(280)
        self.audiosizer.Add(self.synthbutton, 0, wx.ALIGN_CENTER | wx.ALL, border=5)

        self.audiobutton.Bind(wx.EVT_BUTTON, self.pause_play)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.synthbutton.Bind(wx.EVT_BUTTON, self.open_synth)

        #add both components to 1 sizer
        self.mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mainsizer.Add(self.graphsizer, 1)
        self.mainsizer.Add(self.audiosizer, 1, wx.RIGHT)
        self.panel.SetSizer(self.mainsizer)
        self.Fit()
        self.panel.Layout()

        plt.ion()
        #prep timer
        self.timercount = 0
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.record, self.timer)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.timer.Start(100)

    def record(self, event):
        if(self.stream and self.stream.is_active()):
            data = np.frombuffer(self.stream.read(1024, exception_on_overflow=False), dtype=np.float32)
            note = self.notes_o(data)[0]
            peak = np.average(np.abs(data)) * 2000
            # bars = "#" * int(50 * peak / 2 ** 16)

            if (note != 0):
                self.notetext.SetLabel(self.miditonote.get(note))
                if self.synth:
                    self.synth.input_note.SetValue(self.miditonote.get(note))

            #print("%04d %04d %.1f %s" % (self.timercount, peak, note, self.miditonote.get(note)))
            self.xs.append(self.timercount)
            self.timercount += 1
            self.ys.append(peak)
            self.line.set_data(self.xs, self.ys)
            self.ax.relim()
            self.ax.autoscale()
            plt.plot()

    def pause_play(self, event):
        if(self.audiobutton.GetLabel() == "Pause"):
            self.stream.stop_stream()
            self.audiobutton.SetLabel("Play")
        elif(self.audiobutton.GetLabel() == "Play"):
            self.stream.start_stream()
            self.audiobutton.SetLabel("Pause")

    def open_synth(self, event):
        if not self.parent.synth and not self.synth:
            self.synth = SynthWindow(self)

    def OnPaint(self, event):
        # draw octave bar
        self.dc = wx.PaintDC(self)
        self.dc.Clear()
        #grab note octave number
        if self.notetext.GetLabel() != "":
            octaveno = int(self.notetext.GetLabel()[-1])
        else:
            octaveno = -1

        # set pen and brush color to rainbow color
        self.dc.SetPen(wx.Pen("red", style=wx.SOLID))
        if octaveno > 6:
            self.dc.SetBrush(wx.Brush("red", style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 150, 50, 25)

        self.dc.SetPen(wx.Pen(wx.Colour(255,165,0), style=wx.SOLID))
        if octaveno > 5:
            self.dc.SetBrush(wx.Brush(wx.Colour(255,165,0), style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 180, 50, 25)

        self.dc.SetPen(wx.Pen("yellow", style=wx.SOLID))
        if octaveno > 4:
            self.dc.SetBrush(wx.Brush("yellow", style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 210, 50, 25)

        self.dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), style=wx.SOLID))
        if octaveno > 3:
            self.dc.SetBrush(wx.Brush(wx.Colour(0,255,0), style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 240, 50, 25)

        self.dc.SetPen(wx.Pen("blue", style=wx.SOLID))
        if octaveno > 2:
            self.dc.SetBrush(wx.Brush("blue", style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 270, 50, 25)

        self.dc.SetPen(wx.Pen(wx.Colour(63,0,255), style=wx.SOLID))
        if octaveno > 1:
            self.dc.SetBrush(wx.Brush(wx.Colour(63,0,255), style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 300, 50, 25)

        self.dc.SetPen(wx.Pen(wx.Colour(128, 0, 128), style=wx.SOLID))
        if octaveno > 0:
            self.dc.SetBrush(wx.Brush(wx.Colour(128,0,128), style=wx.SOLID))
        else:
            self.dc.SetBrush(wx.NullBrush)
        self.dc.DrawRectangle(720, 330, 50, 25)

        self.panel.Refresh()

    def OnClose(self, event):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()
        if self.canvas:
            self.canvas.Destroy()
        if self.dc:
            self.dc.Destroy()
        if self.synth:
            self.synth.Destroy()
        plt.close('all')
        self.Destroy()
        self.parent.audio = None
        self.parent.Destroy()

if __name__ == "__main__":
    app = wx.App()
    frame = MenuWindow()
    app.MainLoop()
