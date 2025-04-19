from tie.core import Tie

tie = Tie("tie.yaml", 
          default_locale="ru", 
          merge_conflict="override")
print(tie.set_locale("gr").render_tree(one_locale_only=True))
