
mod tables;

#[doc(inline)]
pub use tables::UNICODE_VERSION;

#[doc(inline)]
pub use tables::ideographset_data::IdeographSet;

impl IdeographSet {
    pub fn is_cjkui_in_iicore(self) -> bool {
        matches!(
            self,
            IdeographSet::IICoreCJKUnifiedIdeograph | IdeographSet::IICoreAndUnihanCoreCJKUnifiedIdeograph
        )
    }
    pub fn is_cjkui_in_unihancore(self) -> bool {
        matches!(self, IdeographSet::IICoreAndUnihanCoreCJKUnifiedIdeograph)
    }
    pub fn is_cjk_compat_ideograph(self) -> bool {
        matches!(self, IdeographSet::CJKCompatIdeograph)
    }
    pub fn is_ideograph(self) -> bool {
        !matches!(self, IdeographSet::CJKRadicalAndComponent | 
            IdeographSet::TangutRadicalAndComponent | 
            IdeographSet::Other)
    }
}

pub trait UnicodeIdeographSet {
    fn ideograph_set(&self) -> IdeographSet;
}

impl UnicodeIdeographSet for char {
    fn ideograph_set(&self) -> IdeographSet {
        tables::ideographset_data::ideographset_data_lookup(*self)
    }
}
