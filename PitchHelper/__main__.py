import pyaudio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
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

    def OnRecord(self, event):
        self.audio = RecordWindow()
        self.audio.main()

    def OnOpenSynth(self, event):
        self.synth = SynthWindow()

    def OnClose(self, event):
        self.Destroy()

class SynthWindow(wx.Frame):
    def __init__(self):
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
        if not os.path.exists(os.getcwd() + "/PitchHelper/Notes"):
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

        path = os.getcwd() + "/PitchHelper/Notes/"
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
        if self.stream:
            self.stream.close()
        if self.p:
            self.p.terminate()
        self.Destroy()

class RecordWindow(wx.Frame):
    def __init__(self):
        #super().__init__(parent=None, title='Audio Recorder')
        plt.style.use('ggplot')

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paFloat32, channels=1, rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

        win_s = 4096
        hop_s = CHUNK
        self.notes_o = aubio.notes("default", win_s, hop_s, RATE)

        self.xs = []
        self.ys = []
        self.fig, self.ax = plt.subplots()
        self.line, = self.ax.plot([], [])

        # scrape midi number to note conversion data online
        self.miditonote = {}
        url = "https://www.inspiredacoustics.com/en/MIDI_note_numbers_and_center_frequencies"
        page = get(url, timeout=5)
        soup = BeautifulSoup(page.content, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')

        for row in rows:
            col = row.find_all('td')
            if col[0].text.isdigit():
                midinumber = int(col[0].text)
                self.miditonote[midinumber] = col[3].text



    def initani(self):
        self.ax.set_xlim(0, 300)
        self.ax.set_ylim(0, 3000)
        self.line.set_data(self.xs,self.ys)
        return self.line,

    def animate(self, i):
        data = np.frombuffer(self.stream.read(1024, exception_on_overflow=False), dtype=np.float32)
        note = self.notes_o(data)[0]
        peak = np.average(np.abs(data)) * 2
        #bars = "#" * int(50 * peak / 2 ** 16)

        print("%04d %.1f %s" % (i, note, self.miditonote.get(note)))
        self.xs.append(i)
        self.ys.append(peak)
        self.line.set_data(self.xs, self.ys)
        self.ax.relim()
        self.ax.autoscale()
        return (self.line,)

    def main(self):

        anim = animation.FuncAnimation(self.fig, self.animate, init_func=self.initani, interval=100, blit=False, repeat=False,)
        plt.show()
        #anim.save('./audio.gif', writer='imagemagick', fps=10)
        #print("Saved")

        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    app = wx.App()
    frame = MenuWindow()
    app.MainLoop()
