import time


class EventObject:
    def __init__(self, text: str, context: str, static: bool = False):
        self.text = text
        self.created = int(time.time())
        self.static = static
        self.context = context


class EventTypeForManager:
    current_voice_chat_members = "Текущие участники голосового чата (кто сейчас находится в нём)"
    voice_chat_text_messages = "Сообщения в текстовом канале, привязанном к голосовому чату"
    voice_chat_joins = "Подключения / отключения от голосового канала"

class EventManager:
    def __init__(self):
        self.events = []

    def get_events(self, contexts: list[str], minutes: int = 5, return_static: bool = True) -> list[EventObject]:
        """Get events for the last X minutes or static events with specified contexts"""
        current_time = int(time.time())
        time_threshold = current_time - (minutes * 60)

        if return_static:
            return [event for event in self.events if event.context in contexts]
        else:
            return [
                event for event in self.events
                if event.context in contexts
                   and event.created >= time_threshold
                   and not event.static
            ]

    def create_event(self, text: str, context: str, static: bool = False) -> EventObject:
        print("event", text)
        """Create and add a new event"""
        event = EventObject(text, context, static)
        self.events.append(event)
        return event

    def remove_events(self, context: str) -> None:
        """Remove all events with the specified context"""
        self.events = [event for event in self.events if event.context != context]

    def format_events(self, events: list[EventObject], max_length: int = None, n_hashtags=1) -> str:
        """Format the list of events with a maximum length limit, showing time for non-static events"""
        if not events:
            return ""

        # Sort events by time (newest first)
        sorted_events = sorted(events, key=lambda x: x.created, reverse=True)
        current_time = int(time.time())

        # Group events by context
        contexts = {}
        for event in sorted_events:
            if event.context not in contexts:
                contexts[event.context] = []
            if event.static:
                contexts[event.context].append(event.text)
            else:
                # Calculate time difference
                time_diff = current_time - event.created
                if time_diff < 60:
                    time_str = f"({time_diff} секунд назад)"
                elif time_diff < 3600:
                    minutes = time_diff // 60
                    time_str = f"({minutes} минут{'у' if minutes == 1 else 'ы'} назад)"
                else:
                    hours = time_diff // 3600
                    time_str = f"({hours} час{'ов' if hours > 1 else ''} назад)"
                contexts[event.context].append(f"{time_str} | {event.text}")

        # Format output with max_length consideration
        result = []
        current_length = 0

        for context, texts in contexts.items():
            # Add context header
            context_header = (n_hashtags * "#") + f" {context}"
            if max_length is not None:
                if current_length + len(context_header) > max_length:
                    break
                current_length += len(context_header)
            result.append(context_header)

            # Add messages until max_length is exceeded
            for text in texts:
                if max_length is not None:
                    if current_length + len(text) > max_length:
                        current_length += len(text)
                        break
                result.append(text)

        return "\n".join(result)


# Example usage:
if __name__ == "__main__":
    event_manager = EventManager()

    # Create events
    event_manager.create_event("User1, User2", EventTypeForManager.current_voice_chat_members, static=True)
    event_manager.create_event("User3, User4", EventTypeForManager.current_voice_chat_members, static=True)
    time.sleep(3)
    event_manager.create_event("Hello everyone!", EventTypeForManager.voice_chat_text_messages, static=False)
    time.sleep(5)
    event_manager.create_event("How are you?", EventTypeForManager.voice_chat_text_messages, static=False)
    time.sleep(8)
    event_manager.create_event("User3 joined", EventTypeForManager.current_voice_chat_members, static=False)

    # Get all events before removal
    contexts = [
        EventTypeForManager.current_voice_chat_members,
        EventTypeForManager.voice_chat_text_messages
    ]
    print("Before removal:")
    all_events = event_manager.get_events(contexts, return_static=True)
    print(event_manager.format_events(all_events, max_length=500))
    print()

    # Remove all events with voice_chat_text_messages context
    event_manager.remove_events(EventTypeForManager.current_voice_chat_members)

    # Get events after removal
    print("After removing text messages:")
    remaining_events = event_manager.get_events(contexts, return_static=True)
    print(event_manager.format_events(remaining_events, max_length=500))
