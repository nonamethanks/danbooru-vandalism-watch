import discord
from danboorutools import logger
from discord import Color
from discord.types.embed import Embed


class Styles:
    active = discord.ButtonStyle.green
    revert = discord.ButtonStyle.grey


class Labels:
    handled = "Mark handled"
    not_handled = "Undo mark handled"

    false_positive = "Mark false positive"
    not_false_positive = "Undo false positive"


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label=Labels.handled, style=Styles.active, custom_id="persistent_view:green")
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.can_click_button(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message("Only builders and above can do this. Gomen...", ephemeral=True)
            self.log_click(interaction, button, False)
            return

        self.log_click(interaction, button, True)

        embed = interaction.message.embeds[0]  # type: ignore[union-attr]

        original_label = Labels.handled
        undo_label = Labels.not_handled
        is_revert = button.label != original_label

        embed = self.edit_embed(
            embed,
            is_revert,
            interaction.user,  # type: ignore[arg-type]  # I FUCKING HATE MYPY I FUCKING HATE MYPY
            default_color=Color.green(),
        )
        assert embed.title
        embed.title = embed.title.removesuffix("(Handled)").strip() if is_revert else f"{embed.title} (Handled)"

        self.fix_buttons(button, original_label, undo_label)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label=Labels.false_positive, style=Styles.active, custom_id="persistent_view:grey")
    async def grey(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.can_click_button(interaction.user):  # type: ignore[arg-type]
            await interaction.response.send_message("Only builders and above can do this. Gomen...", ephemeral=True)
            self.log_click(interaction, button, False)
            return

        self.log_click(interaction, button, True)

        embed = interaction.message.embeds[0]  # type: ignore[union-attr, misc]

        original_label = Labels.false_positive
        undo_label = Labels.not_false_positive

        is_revert = button.label != original_label

        embed = self.edit_embed(
            embed,
            is_revert,
            interaction.user,  # type: ignore[arg-type]  # I FUCKING HATE MYPY I FUCKING HATE MYPY
            default_color=Color.dark_grey(),
        )
        assert embed.title
        embed.title = embed.title.removesuffix("(Handled)").strip() if is_revert else f"{embed.title} (False Positive)"

        self.fix_buttons(button, original_label, undo_label)
        await interaction.response.edit_message(embed=embed, view=self)

    def edit_embed(
        self,
        embed: discord.Embed,
        is_revert: bool,
        editor: discord.Member,
        default_color: Color,
    ) -> discord.Embed:
        ####################################################################################

        embed.colour = Color.red() if is_revert else default_color
        embed_dict = embed.to_dict()
        self.toggle_field_strike(embed_dict, is_revert=is_revert)
        self.set_last_editors(embed_dict, editor)
        embed = discord.Embed.from_dict(embed_dict)

        return embed

    def fix_buttons(self, button: discord.ui.Button, original_label: str, undo_label: str) -> None:
        if button.label == original_label:
            button.label = undo_label
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    child.style = Styles.revert
            button.disabled = False
        else:
            button.label = original_label
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = False
                    child.style = Styles.active

    def toggle_field_strike(self, embed_dict: Embed, is_revert: bool = True) -> None:
        for field in embed_dict["fields"]:
            if field["name"] == "Last handled by":
                continue

            if field["name"] == "\u200b":
                continue

            if is_revert:
                field["name"] = field["name"].strip("~")
                field["value"] = field["value"].strip("~")
            else:
                field["name"] = f"~~{field['name']}~~"
                field["value"] = f"~~{field['value']}~~"

    def set_last_editors(self, embed_dict: Embed, last_editor: discord.Member) -> None:
        try:
            editor_field = [f for f in embed_dict["fields"] if f["name"] == "Last handled by"][0]
        except IndexError:
            editor_field = {"name": "Last handled by", "value": f"<@{last_editor.id}>", "inline": False}
            embed_dict["fields"].append(editor_field)
        else:
            editor_field["value"] = f"<@{last_editor.id}>"

    def can_click_button(self, user: discord.Member) -> bool:
        user_roles = {r.name.lower() for r in user.roles}
        acceptable_roles = {"builder", "mod", "admin"}
        return bool(user_roles & acceptable_roles)

    def log_click(self, interaction: discord.Interaction, button: discord.ui.Button, success: bool) -> None:
        assert interaction.message
        if success:
            logger.info(
                f"Discord user #{interaction.user.name} ({interaction.user.display_name}) "
                f"successfully clicked '{button.label}' on {interaction.message.jump_url}",
            )
        else:
            logger.info(
                f"Discord user #{interaction.user.name} ({interaction.user.display_name}) "
                f"tried to click '{button.label}' on {interaction.message.jump_url} but didn't have the right roles.",
            )
