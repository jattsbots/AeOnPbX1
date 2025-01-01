from bot.core.config_manager import Config

i = Config.CMD_SUFFIX


class _BotCommands:
    def __init__(self):
        self.StartCommand = f"start{i}"
        self.MirrorCommand = [f"mirror{i}", f"m{i}"]
        self.YtdlCommand = [f"ytdl{i}", f"y{i}"]
        self.LeechCommand = [f"leech{i}", f"l{i}"]
        self.YtdlLeechCommand = [f"ytdlleech{i}", f"yl{i}"]
        self.CloneCommand = f"clone{i}"
        self.CountCommand = f"count{i}"
        self.DeleteCommand = f"del{i}"
        self.CancelAllCommand = f"cancelall{i}"
        self.ForceStartCommand = [f"forcestart{i}", f"fs{i}"]
        self.ListCommand = f"list{i}"
        self.SearchCommand = f"search{i}"
        self.StatusCommand = f"status{i}"
        self.UsersCommand = f"users{i}"
        self.AuthorizeCommand = f"authorize{i}"
        self.UnAuthorizeCommand = f"unauthorize{i}"
        self.AddSudoCommand = f"addsudo{i}"
        self.RmSudoCommand = f"rmsudo{i}"
        self.PingCommand = f"ping{i}"
        self.RestartCommand = f"restart{i}"
        self.RestartSessionsCommand = f"restartses{i}"
        self.StatsCommand = f"stats{i}"
        self.HelpCommand = f"help{i}"
        self.LogCommand = f"log{i}"
        self.ShellCommand = f"shell{i}"
        self.AExecCommand = f"aexec{i}"
        self.ExecCommand = f"exec{i}"
        self.ClearLocalsCommand = f"clearlocals{i}"
        self.BotSetCommand = f"botsettings{i}"
        self.UserSetCommand = f"settings{i}"
        self.SelectCommand = f"sel{i}"
        self.RssCommand = f"rss{i}"


BotCommands = _BotCommands()
