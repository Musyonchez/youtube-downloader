#!/usr/bin/env python3
"""YouTube Downloader - Interactive TUI for downloading YouTube audio as MP3."""
import sys
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from utils import Storage
from search import YouTubeSearcher
from downloader import YouTubeDownloader

console = Console()
storage = Storage()
searcher = YouTubeSearcher()


def print_header():
    """Print application header."""
    console.clear()
    header = Text()
    header.append("YouTube MP3 Downloader", style="bold cyan")
    console.print(Panel(header, border_style="cyan"))
    console.print()


def display_library():
    """Display current library queue."""
    library = storage.load_library()

    if not library:
        console.print("[yellow]Library is empty. Add some videos first![/yellow]\n")
        return

    table = Table(title="Library Queue", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="cyan")
    table.add_column("Channel", style="green")
    table.add_column("Duration", style="yellow", width=10)

    for i, item in enumerate(library, 1):
        table.add_row(
            str(i),
            item['title'][:50] + "..." if len(item['title']) > 50 else item['title'],
            item['channel'][:30] + "..." if len(item['channel']) > 30 else item['channel'],
            item['duration']
        )

    console.print(table)
    console.print(f"\n[bold]Total items in queue: {len(library)}[/bold]\n")


def display_stats():
    """Display download statistics."""
    library = storage.load_library()
    downloaded = storage.load_downloaded()

    console.print(f"[cyan]📥 In Queue:[/cyan] {len(library)}")
    console.print(f"[green]✓ Downloaded:[/green] {len(downloaded)}")
    console.print()


def search_by_name():
    """Search YouTube by name."""
    print_header()
    console.print("[bold cyan]Search YouTube by Name[/bold cyan]\n")

    query = questionary.text("Enter search query:").ask()
    if not query:
        return

    results = searcher.search_by_name(query, limit=15)

    if not results:
        console.print("[red]No results found[/red]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    # Format choices with status indicators
    choices = []
    for i, video in enumerate(results, 1):
        status = storage.get_item_status(video['video_id'])

        if status == 'downloaded':
            indicator = "[green]✓[/green]"
            style = "dim"
        elif status == 'queued':
            indicator = "[yellow]📥[/yellow]"
            style = ""
        else:
            indicator = "[cyan]○[/cyan]"
            style = ""

        title = video['title'][:60] + "..." if len(video['title']) > 60 else video['title']
        channel = video['channel'][:25] + "..." if len(video['channel']) > 25 else video['channel']

        choice_text = f"{indicator} {title} - {channel} ({video['duration']})"
        choices.append({
            'name': choice_text,
            'value': i - 1,
            'disabled': status == 'downloaded'
        })

    choices.append({'name': '← Back to menu', 'value': -1})

    console.print()
    selected = questionary.select(
        "Select videos to add to library (✓=Downloaded, 📥=Queued, ○=New):",
        choices=choices
    ).ask()

    if selected == -1 or selected is None:
        return

    video = results[selected]
    status = storage.get_item_status(video['video_id'])

    if status == 'queued':
        console.print("[yellow]This video is already in your library queue[/yellow]")
    elif status == 'downloaded':
        console.print("[yellow]This video has already been downloaded[/yellow]")
    else:
        storage.add_to_library(video)
        console.print(f"[green]✓ Added to library: {video['title']}[/green]")

    questionary.press_any_key_to_continue("\nPress any key to continue...").ask()


def add_by_url():
    """Add video by URL."""
    print_header()
    console.print("[bold cyan]Add by URL[/bold cyan]\n")

    url = questionary.text("Enter YouTube URL:").ask()
    if not url:
        return

    # Validate URL
    is_valid, url_type = searcher.validate_url(url)

    if not is_valid:
        console.print("[red]Invalid YouTube URL[/red]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    if url_type == 'playlist':
        console.print("[yellow]This is a playlist URL. Use 'Add by Playlist URL' option instead.[/yellow]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    # Get video info
    video_info = searcher.get_video_info(url)

    if not video_info:
        console.print("[red]Could not fetch video information[/red]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    # Check status
    status = storage.get_item_status(video_info['video_id'])

    console.print(f"\n[cyan]Title:[/cyan] {video_info['title']}")
    console.print(f"[cyan]Channel:[/cyan] {video_info['channel']}")
    console.print(f"[cyan]Duration:[/cyan] {video_info['duration']}")

    if status == 'downloaded':
        console.print("\n[yellow]✓ This video has already been downloaded[/yellow]")
    elif status == 'queued':
        console.print("\n[yellow]📥 This video is already in your library queue[/yellow]")
    else:
        storage.add_to_library(video_info)
        console.print("\n[green]✓ Added to library[/green]")

    questionary.press_any_key_to_continue("\nPress any key to continue...").ask()


def add_by_playlist():
    """Add videos from playlist URL."""
    print_header()
    console.print("[bold cyan]Add by Playlist URL[/bold cyan]\n")

    url = questionary.text("Enter YouTube playlist URL:").ask()
    if not url:
        return

    # Validate URL
    is_valid, url_type = searcher.validate_url(url)

    if not is_valid or url_type != 'playlist':
        console.print("[red]Invalid playlist URL[/red]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    # Get playlist videos
    videos = searcher.get_playlist_videos(url)

    if not videos:
        console.print("[red]Could not fetch playlist or playlist is empty[/red]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    # Count status
    new_count = 0
    queued_count = 0
    downloaded_count = 0

    for video in videos:
        status = storage.get_item_status(video['video_id'])
        if status == 'new':
            new_count += 1
        elif status == 'queued':
            queued_count += 1
        elif status == 'downloaded':
            downloaded_count += 1

    console.print(f"\n[bold]Playlist Summary:[/bold]")
    console.print(f"[cyan]○ New videos:[/cyan] {new_count}")
    console.print(f"[yellow]📥 Already queued:[/yellow] {queued_count}")
    console.print(f"[green]✓ Already downloaded:[/green] {downloaded_count}")
    console.print()

    if new_count == 0:
        console.print("[yellow]No new videos to add[/yellow]")
        questionary.press_any_key_to_continue("Press any key to continue...").ask()
        return

    add_all = questionary.confirm(
        f"Add all {new_count} new videos to library?",
        default=True
    ).ask()

    if add_all:
        added = 0
        for video in videos:
            if storage.get_item_status(video['video_id']) == 'new':
                storage.add_to_library(video)
                added += 1

        console.print(f"\n[green]✓ Added {added} videos to library[/green]")
    else:
        console.print("[yellow]Cancelled[/yellow]")

    questionary.press_any_key_to_continue("\nPress any key to continue...").ask()


def manage_library():
    """Manage library queue."""
    while True:
        print_header()
        console.print("[bold cyan]Manage Library[/bold cyan]\n")
        display_library()

        library = storage.load_library()
        if not library:
            questionary.press_any_key_to_continue("Press any key to continue...").ask()
            return

        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Remove item from library",
                "Clear entire library",
                "← Back to menu"
            ]
        ).ask()

        if action == "← Back to menu" or action is None:
            return

        if action == "Clear entire library":
            confirm = questionary.confirm("Are you sure you want to clear the entire library?").ask()
            if confirm:
                storage.clear_library()
                console.print("[green]✓ Library cleared[/green]")
                questionary.press_any_key_to_continue("Press any key to continue...").ask()
                return

        elif action == "Remove item from library":
            choices = [
                {'name': f"{i}. {item['title'][:60]}", 'value': item['video_id']}
                for i, item in enumerate(library, 1)
            ]
            choices.append({'name': '← Cancel', 'value': None})

            video_id = questionary.select("Select item to remove:", choices=choices).ask()

            if video_id:
                storage.remove_from_library(video_id)
                console.print("[green]✓ Item removed[/green]")
                questionary.press_any_key_to_continue("Press any key to continue...").ask()


def download_library():
    """Download all items in library."""
    print_header()
    console.print("[bold cyan]Download Library[/bold cyan]\n")

    library = storage.load_library()

    if not library:
        console.print("[yellow]Library is empty. Nothing to download.[/yellow]")
        questionary.press_any_key_to_continue("\nPress any key to continue...").ask()
        return

    console.print(f"[bold]Ready to download {len(library)} items[/bold]\n")

    for i, item in enumerate(library[:5], 1):  # Show first 5
        console.print(f"{i}. {item['title'][:60]}")

    if len(library) > 5:
        console.print(f"... and {len(library) - 5} more")

    console.print()
    confirm = questionary.confirm("Start downloading?", default=True).ask()

    if not confirm:
        return

    # Get config
    config = storage.load_config()
    downloader = YouTubeDownloader(
        download_dir=config['download_dir'],
        audio_quality=config['audio_quality']
    )

    # Download all
    results = downloader.download_batch(library)

    # Move successful downloads to downloaded list and remove from library
    for result in results:
        if result['success']:
            storage.add_to_downloaded(result)
            storage.remove_from_library(result['video_id'])

    questionary.press_any_key_to_continue("\nPress any key to continue...").ask()


def settings():
    """Configure settings."""
    print_header()
    console.print("[bold cyan]Settings[/bold cyan]\n")

    config = storage.load_config()

    console.print(f"[cyan]Current Settings:[/cyan]")
    console.print(f"  Audio Quality: {config['audio_quality']}kbps")
    console.print(f"  Download Directory: {config['download_dir']}")
    console.print()

    action = questionary.select(
        "What would you like to change?",
        choices=[
            "Audio Quality",
            "Download Directory",
            "← Back to menu"
        ]
    ).ask()

    if action == "← Back to menu" or action is None:
        return

    if action == "Audio Quality":
        quality = questionary.select(
            "Select audio quality:",
            choices=["128", "192", "256", "320"]
        ).ask()

        if quality:
            storage.update_config(audio_quality=quality)
            console.print(f"[green]✓ Audio quality set to {quality}kbps[/green]")

    elif action == "Download Directory":
        directory = questionary.text(
            "Enter download directory:",
            default=config['download_dir']
        ).ask()

        if directory:
            storage.update_config(download_dir=directory)
            console.print(f"[green]✓ Download directory updated[/green]")

    questionary.press_any_key_to_continue("\nPress any key to continue...").ask()


def main_menu():
    """Main application menu."""
    while True:
        print_header()
        display_stats()

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "🔍 Search by name",
                "🔗 Add by URL",
                "📋 Add by playlist URL",
                "📚 View/Manage library",
                "⬇️  Download library",
                "⚙️  Settings",
                "❌ Exit"
            ]
        ).ask()

        if choice is None or "Exit" in choice:
            console.print("\n[cyan]Goodbye![/cyan]\n")
            sys.exit(0)
        elif "Search" in choice:
            search_by_name()
        elif "Add by URL" in choice:
            add_by_url()
        elif "playlist" in choice:
            add_by_playlist()
        elif "library" in choice:
            manage_library()
        elif "Download" in choice:
            download_library()
        elif "Settings" in choice:
            settings()


def main():
    """Application entry point."""
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n\n[cyan]Goodbye![/cyan]\n")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
