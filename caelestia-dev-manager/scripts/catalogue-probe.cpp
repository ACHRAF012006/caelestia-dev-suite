// Desktop acceptance helper; queries the actual KDE application database.
#include <QCoreApplication>
#include <QTextStream>
#include <KApplicationTrader>
#include <KService>
#include <KIO/ApplicationLauncherJob>

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (argc < 2) return 2;
    KService::Ptr entry;
    const bool fromFile = QString::fromLocal8Bit(argv[1]) == "--file";
    if (fromFile) {
        if (argc < 3) return 2;
        entry = KService::Ptr(new KService(QString::fromLocal8Bit(argv[2])));
        if (!entry->isValid()) return 3;
    } else {
    const QString id = QString::fromLocal8Bit(argv[1]);
    auto entries = KApplicationTrader::query([&](const KService::Ptr &service) {
        return service->desktopEntryName() == id && !service->noDisplay();
    });
    if (entries.isEmpty()) return 3;
    entry = entries[0];
    }
    QTextStream(stdout) << entry->name() << "\n" << entry->exec() << "\n";
    const int launchIndex = fromFile ? 3 : 2;
    if (argc > launchIndex && QString::fromLocal8Bit(argv[launchIndex]) == "--launch") {
        auto *job = new KIO::ApplicationLauncherJob(entry);
        QObject::connect(job, &KJob::result, &app, [&](KJob *result) {
            if (result->error()) QTextStream(stderr) << result->errorText() << "\n";
            app.exit(result->error() ? 4 : 0);
        });
        job->start();
        return app.exec();
    }
    return 0;
}
